#!/bin/bash

# Benchmark script for Nginx, Caddy, and Traefik
# This script uses wrk to benchmark the reverse proxies and collects system metrics

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Reverse Proxy Benchmark${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Configuration
DURATION=30
THREADS=4
CONNECTIONS=100
RESULTS_DIR="./results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SAMPLE_INTERVAL=0.1
SCHEME=${SCHEME:-https}

curl_opts=(-s)
if [ "$SCHEME" = "https" ]; then
    curl_opts+=(-k)
fi

mkdir -p "$RESULTS_DIR"

# Check if wrk is installed
if ! command -v wrk &> /dev/null; then
    echo -e "${RED}wrk is not installed. Attempting to install via Docker...${NC}"
    USE_DOCKER_WRK=true
else
    USE_DOCKER_WRK=false
fi

get_container_name() {
    local port=$1
    local service=""

    case $port in
        8080) service="nginx" ;;
        8081) service="caddy" ;;
        8082) service="traefik" ;;
        8083) service="haproxy" ;;
    esac

    if [ -z "$service" ]; then
        return 1
    fi

    local container_id=""
    if docker compose version >/dev/null 2>&1; then
        container_id=$(docker compose ps -q "$service" 2>/dev/null)
    fi

    if [ -z "$container_id" ] && command -v docker-compose >/dev/null 2>&1; then
        container_id=$(docker-compose ps -q "$service" 2>/dev/null)
    fi

    if [ -n "$container_id" ]; then
        echo "$container_id"
    else
        local project_name=${COMPOSE_PROJECT_NAME:-$(basename "$(pwd)")}
        echo "${project_name}-${service}-1"
    fi
}

convert_to_mb() {
    local value=$(echo "$1" | tr -d ' ')
    local number=$(echo "$value" | sed -E 's/([0-9.]+).*/\1/')
    local unit=$(echo "$value" | sed -E 's/[0-9.]+(.*)/\1/')

    case "$unit" in
        GiB|GB|G)
            awk -v num="$number" 'BEGIN {printf "%.2f", num * 1024}'
            ;;
        KiB|KB|K)
            awk -v num="$number" 'BEGIN {printf "%.4f", num / 1024}'
            ;;
        B)
            awk -v num="$number" 'BEGIN {printf "%.6f", num / (1024 * 1024)}'
            ;;
        *)
            awk -v num="$number" 'BEGIN {printf "%.2f", num}'
            ;;
    esac
}

monitor_metrics() {
    local container_name=$1
    local output_file=$2
    local duration=$3
    
    echo "timestamp,cpu_percent,memory_mb,memory_percent" > "$output_file"
    
    local end_time=$(($(date +%s) + duration))
    while [ $(date +%s) -lt $end_time ]; do
        local stats=$(docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}}" "$container_name" 2>/dev/null)
        if [ -n "$stats" ]; then
            local cpu_raw=$(echo "$stats" | cut -d',' -f1 | sed 's/%//')
            # Normalize CPU to 0-100% range (Docker reports per-core usage, can exceed 100%)
            local cpu=$(echo "$cpu_raw" | awk '{if ($1 > 100) print 100; else print $1}')
            
            local mem_usage=$(echo "$stats" | cut -d',' -f2)
            local mem_used_raw=$(echo "$mem_usage" | cut -d'/' -f1)
            local mem_total_raw=$(echo "$mem_usage" | cut -d'/' -f2)

            local mem_mb=$(convert_to_mb "$mem_used_raw")
            local mem_total_mb=$(convert_to_mb "$mem_total_raw")

            # Fallback to zero when conversion fails
            mem_mb=${mem_mb:-0}
            mem_total_mb=${mem_total_mb:-0}

            local mem_percent="0.00"
            if awk -v total="$mem_total_mb" 'BEGIN {exit !(total>0)}'; then
                mem_percent=$(awk -v used="$mem_mb" -v total="$mem_total_mb" 'BEGIN {if (total>0) printf "%.2f", (used/total)*100; else printf "0.00"}')
            fi

            echo "$(date +%s.%N),$cpu,$mem_mb,$mem_percent" >> "$output_file"
        fi
        sleep $SAMPLE_INTERVAL
    done
}

run_benchmark() {
    local name=$1
    local port=$2
    local endpoint=$3
    local url="$SCHEME://localhost:$port$endpoint"
    local container_name=$(get_container_name $port)

    echo -e "${YELLOW}Benchmarking $name on port $port ($endpoint)...${NC}"
    echo -e "${YELLOW}Monitoring CPU and Memory...${NC}"

    local base_filename="${name}_fibonacci_${TIMESTAMP}"
    local metrics_file="$RESULTS_DIR/${base_filename}_metrics.csv"
    
    monitor_metrics "$container_name" "$metrics_file" "$DURATION" &
    local monitor_pid=$!

    if [ "$USE_DOCKER_WRK" = true ]; then
        docker run --rm --network host williamyeh/wrk \
            -t${THREADS} -c${CONNECTIONS} -d${DURATION}s \
            --latency "$url" > "$RESULTS_DIR/${base_filename}.txt"
    else
        wrk -t${THREADS} -c${CONNECTIONS} -d${DURATION}s \
            --latency "$url" > "$RESULTS_DIR/${base_filename}.txt"
    fi

    wait $monitor_pid

    echo -e "${GREEN}✓ $name benchmark complete${NC}"
    echo ""
}

# Verify services are running
echo -e "${YELLOW}Verifying services are running...${NC}"
for port in 8080 8081 8082 8083; do
    if ! curl "${curl_opts[@]}" "$SCHEME://localhost:$port/api/health" > /dev/null; then
        echo -e "${RED}Service on port $port is not responding!${NC}"
        echo -e "${RED}Please ensure all services are running with: docker compose up -d${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ All services are running${NC}"
echo ""

# Wait a bit for services to stabilize
sleep 2

# Run benchmarks for fibonacci endpoint only
echo -e "${GREEN}Testing /api/compute/fibonacci endpoint (n=30)${NC}"
echo -e "${GREEN}This computes the 30th Fibonacci number to simulate CPU-intensive work${NC}"
echo ""

run_benchmark "nginx" 8080 "/api/compute/fibonacci?n=30"
sleep 3



run_benchmark "traefik" 8082 "/api/compute/fibonacci?n=30"
sleep 3

run_benchmark "haproxy" 8083 "/api/compute/fibonacci?n=30"
sleep 3

run_benchmark "caddy" 8081 "/api/compute/fibonacci?n=30"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}All benchmarks complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Results saved to: $RESULTS_DIR"
echo "Latest results: *_${TIMESTAMP}.txt"
echo ""
echo -e "${YELLOW}Run 'python3 analyze_results.py $TIMESTAMP' to generate charts${NC}"
