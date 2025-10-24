#!/usr/bin/env python3

import re
import sys
import os
import glob
import csv
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from matplotlib.patches import Rectangle

matplotlib.use('Agg')

DARK_BG = '#1a1a2e'
DARK_SURFACE = '#16213e'
DARK_TEXT = '#e8e8e8'
DARK_TEXT_SECONDARY = '#a8a8a8'
DARK_GRID = '#404040'

COLORS = {
    'nginx': '#60a5fa',
    'caddy': '#34d399',
    'traefik': '#fbbf24',
    'haproxy': '#f87171',
}

LINE_STYLES = {
    'nginx': '-',
    'caddy': '--',
    'traefik': '-.',
    'haproxy': ':',
}

def setup_dark_theme(fig, ax):
    fig.patch.set_facecolor(DARK_BG)
    
    if isinstance(ax, (list, np.ndarray)):
        axes_list = ax.flat if isinstance(ax, np.ndarray) else ax
        for a in axes_list:
            a.set_facecolor(DARK_SURFACE)
            a.tick_params(colors=DARK_TEXT, which='both')
            a.spines['bottom'].set_color(DARK_TEXT_SECONDARY)
            a.spines['left'].set_color(DARK_TEXT_SECONDARY)
            a.spines['top'].set_color(DARK_SURFACE)
            a.spines['right'].set_color(DARK_SURFACE)
            a.xaxis.label.set_color(DARK_TEXT)
            a.yaxis.label.set_color(DARK_TEXT)
            a.title.set_color(DARK_TEXT)
    else:
        ax.set_facecolor(DARK_SURFACE)
        ax.tick_params(colors=DARK_TEXT, which='both')
        ax.spines['bottom'].set_color(DARK_TEXT_SECONDARY)
        ax.spines['left'].set_color(DARK_TEXT_SECONDARY)
        ax.spines['top'].set_color(DARK_SURFACE)
        ax.spines['right'].set_color(DARK_SURFACE)
        ax.xaxis.label.set_color(DARK_TEXT)
        ax.yaxis.label.set_color(DARK_TEXT)
        ax.title.set_color(DARK_TEXT)

class BenchmarkResult:
    def __init__(self, name):
        self.name = name
        self.requests_per_sec = 0
        self.transfer_per_sec = 0
        self.avg_latency = 0
        self.max_latency = 0
        self.stdev_latency = 0
        self.latency_50 = 0
        self.latency_75 = 0
        self.latency_90 = 0
        self.latency_99 = 0
        self.total_requests = 0
        self.total_transfer = 0
        self.cpu_timeline = []
        self.memory_timeline = []
        self.timestamps = []

def parse_metrics_csv(filepath):
    timestamps = []
    cpu_values = []
    memory_values = []
    
    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            start_time = None
            for row in reader:
                timestamp = float(row['timestamp'])
                if start_time is None:
                    start_time = timestamp
                
                relative_time = timestamp - start_time
                timestamps.append(relative_time)
                
                cpu_values.append(float(row['cpu_percent']))
                memory_values.append(float(row['memory_mb']))
    except FileNotFoundError:
        print(f"Error: Metrics file not found: {filepath}")
    except Exception as e:
        print(f"Error parsing metrics file {filepath}: {e}")
    
    return timestamps, cpu_values, memory_values


def parse_wrk_output(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    result = BenchmarkResult(Path(filepath).stem.split('_')[0])

    match = re.search(r'Requests/sec:\s+([\d.]+)', content)
    if match:
        result.requests_per_sec = float(match.group(1))

    match = re.search(r'Transfer/sec:\s+([\d.]+)([KMG]B)', content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 'KB':
            value /= 1024
        elif unit == 'GB':
            value *= 1024
        result.transfer_per_sec = value

    match = re.search(r'Latency\s+([\d.]+)(\w+)', content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 's':
            value *= 1000
        elif unit == 'us':
            value /= 1000
        result.avg_latency = value

    match = re.search(r'50%\s+([\d.]+)(\w+)', content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 's':
            value *= 1000
        elif unit == 'us':
            value /= 1000
        result.latency_50 = value

    match = re.search(r'75%\s+([\d.]+)(\w+)', content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 's':
            value *= 1000
        elif unit == 'us':
            value /= 1000
        result.latency_75 = value

    match = re.search(r'90%\s+([\d.]+)(\w+)', content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 's':
            value *= 1000
        elif unit == 'us':
            value /= 1000
        result.latency_90 = value

    match = re.search(r'99%\s+([\d.]+)(\w+)', content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 's':
            value *= 1000
        elif unit == 'us':
            value /= 1000
        result.latency_99 = value

    match = re.search(r'([\d.]+)([KM])?\s+requests in', content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 'K':
            value *= 1000
        elif unit == 'M':
            value *= 1000000
        result.total_requests = int(value)

    metrics_file = filepath.replace('.txt', '_metrics.csv')
    if os.path.exists(metrics_file):
        timestamps, cpu_values, memory_values = parse_metrics_csv(metrics_file)
        result.timestamps = timestamps
        result.cpu_timeline = cpu_values
        result.memory_timeline = memory_values

    return result

def create_time_series_chart(results, output_dir='charts'):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))
    setup_dark_theme(fig, [ax1, ax2])
    
    for result in results:
        if result.timestamps and result.cpu_timeline:
            ax1.plot(result.timestamps, result.cpu_timeline, 
                    label=result.name.capitalize(),
                    color=COLORS[result.name],
                    linestyle=LINE_STYLES[result.name],
                    linewidth=2.5,
                    alpha=0.9,
                    marker='o',
                    markersize=2,
                    markevery=max(1, len(result.timestamps) // 30))
    
    ax1.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold', color=DARK_TEXT)
    ax1.set_ylabel('CPU Usage (%)', fontsize=12, fontweight='bold', color=DARK_TEXT)
    ax1.set_title('CPU Usage Over Time During Benchmark', fontsize=14, fontweight='bold', pad=15, color=DARK_TEXT)
    legend1 = ax1.legend(loc='best', fontsize=11, framealpha=0.95, shadow=False, 
                        facecolor=DARK_SURFACE, edgecolor=DARK_TEXT_SECONDARY)
    for text in legend1.get_texts():
        text.set_color(DARK_TEXT)
    ax1.grid(True, alpha=0.15, linestyle='--', linewidth=0.6, color=DARK_GRID)
    ax1.set_xlim(left=0)
    ax1.set_ylim(bottom=0)
    
    for result in results:
        if result.timestamps and result.memory_timeline:
            ax2.plot(result.timestamps, result.memory_timeline,
                    label=result.name.capitalize(),
                    color=COLORS[result.name],
                    linestyle=LINE_STYLES[result.name],
                    linewidth=2.5,
                    alpha=0.9,
                    marker='s',
                    markersize=2,
                    markevery=max(1, len(result.timestamps) // 30))
    
    ax2.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold', color=DARK_TEXT)
    ax2.set_ylabel('Memory Usage (MB)', fontsize=12, fontweight='bold', color=DARK_TEXT)
    ax2.set_title('Memory Usage Over Time During Benchmark', fontsize=14, fontweight='bold', pad=15, color=DARK_TEXT)
    legend2 = ax2.legend(loc='best', fontsize=11, framealpha=0.95, shadow=False,
                        facecolor=DARK_SURFACE, edgecolor=DARK_TEXT_SECONDARY)
    for text in legend2.get_texts():
        text.set_color(DARK_TEXT)
    ax2.grid(True, alpha=0.15, linestyle='--', linewidth=0.6, color=DARK_GRID)
    ax2.set_xlim(left=0)
    ax2.set_ylim(bottom=0)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/resource_usage_timeline.png', dpi=300, bbox_inches='tight', facecolor=DARK_BG)
    print(f"✓ Created {output_dir}/resource_usage_timeline.png")
    plt.close()

def create_throughput_chart(results, output_dir='charts'):
    fig, ax = plt.subplots(figsize=(10, 4))
    setup_dark_theme(fig, ax)
    
    names = [r.name.capitalize() for r in results]
    rps_values = [r.requests_per_sec for r in results]
    colors = [COLORS[r.name] for r in results]
    
    y_pos = np.arange(len(names))
    
    bars = ax.barh(y_pos, rps_values, height=0.8, color=colors, alpha=0.9, 
                   edgecolor=DARK_TEXT_SECONDARY, align='center', linewidth=.1)
    
    ax.set_xlabel('Requests per Second', fontsize=12, fontweight='bold', color=DARK_TEXT)
    ax.set_title('Throughput Comparison - Fibonacci Endpoint (n=30)', 
                fontsize=14, fontweight='bold', pad=30, color=DARK_TEXT)
    ax.grid(axis='x', alpha=0.2, linestyle='--', color=DARK_GRID)
    
    ax.set_yticks([])
    ax.set_yticklabels([])
    
    for i, (bar, name) in enumerate(zip(bars, names)):
        width = bar.get_width()
        ax.text(width * 1.02, bar.get_y() + bar.get_height()/2.,
                f'{width:.0f} req/s',
                ha='left', va='center', fontweight='bold', fontsize=11, color=DARK_TEXT)
    
    x_max = max(rps_values) * 1.45
    ax.set_xlim(0, x_max)
    
    ax.set_ylim(-2, len(names) + 0.8)
    
    legend_elements = []
    for i, (name, color) in enumerate(zip(names, colors)):
        legend_elements.append(Rectangle((0, 0), 1, 1, fc=color, edgecolor=DARK_TEXT_SECONDARY, 
                                        linewidth=1.2, alpha=0.9))
    
    legend = ax.legend(legend_elements, names, 
                      loc='upper center',
                      bbox_to_anchor=(0.5, 1.12),
                      ncol=len(names),
                      frameon=True,
                      framealpha=0.95,
                      facecolor=DARK_SURFACE,
                      edgecolor=DARK_TEXT_SECONDARY,
                      fontsize=11,
                      handlelength=1.5,
                      handleheight=1.2,
                      columnspacing=1.5)
    
    for text in legend.get_texts():
        text.set_color(DARK_TEXT)
        text.set_fontweight('bold')
    
    fig.text(0.5, 0.01, 'Higher values indicate better performance', 
            ha='center', fontsize=10, style='italic', color=DARK_TEXT_SECONDARY)
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(f'{output_dir}/throughput.png', dpi=300, bbox_inches='tight', facecolor=DARK_BG)
    print(f"✓ Created {output_dir}/throughput.png")
    plt.close()

def create_latency_chart(results, output_dir='charts'):
    fig, ax = plt.subplots(figsize=(10, 4))
    setup_dark_theme(fig, ax)
    
    names = [r.name.capitalize() for r in results]
    latency_values = [r.avg_latency for r in results]
    colors = [COLORS[r.name] for r in results]
    
    y_pos = np.arange(len(names))
    
    bars = ax.barh(y_pos, latency_values, height=0.8, color=colors, alpha=0.9,
                   edgecolor=DARK_TEXT_SECONDARY, align='center', linewidth=.1)
    
    ax.set_xlabel('Latency (milliseconds)', fontsize=12, fontweight='bold', color=DARK_TEXT)
    ax.set_title('Average Response Latency Comparison', 
                fontsize=14, fontweight='bold', pad=30, color=DARK_TEXT)
    ax.grid(axis='x', alpha=0.2, linestyle='--', color=DARK_GRID)
    
    ax.set_yticks([])
    ax.set_yticklabels([])
    
    for i, (bar, name) in enumerate(zip(bars, names)):
        width = bar.get_width()
        ax.text(width * 1.02, bar.get_y() + bar.get_height()/2.,
                f'{width:.2f} ms',
                ha='left', va='center', fontweight='bold', fontsize=11, color=DARK_TEXT)
    
    x_max = max(latency_values) * 1.45
    ax.set_xlim(0, x_max)
    
    ax.set_ylim(-2, len(names) + 0.8)
    
    legend_elements = []
    for i, (name, color) in enumerate(zip(names, colors)):
        legend_elements.append(Rectangle((0, 0), 1, 1, fc=color, edgecolor=DARK_TEXT_SECONDARY, 
                                        linewidth=1.2, alpha=0.9))
    
    legend = ax.legend(legend_elements, names, 
                      loc='upper center',
                      bbox_to_anchor=(0.5, 1.12),
                      ncol=len(names),
                      frameon=True,
                      framealpha=0.95,
                      facecolor=DARK_SURFACE,
                      edgecolor=DARK_TEXT_SECONDARY,
                      fontsize=11,
                      handlelength=1.5,
                      handleheight=1.2,
                      columnspacing=1.5)
    
    for text in legend.get_texts():
        text.set_color(DARK_TEXT)
        text.set_fontweight('bold')
    
    fig.text(0.5, 0.01, 'Lower values indicate better performance', 
            ha='center', fontsize=10, style='italic', color=DARK_TEXT_SECONDARY)
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(f'{output_dir}/latency.png', dpi=300, bbox_inches='tight', facecolor=DARK_BG)
    print(f"✓ Created {output_dir}/latency.png")
    plt.close()

def create_latency_percentiles_chart(results, output_dir='charts'):
    fig, ax = plt.subplots(figsize=(14, 8))
    setup_dark_theme(fig, ax)
    
    names = [r.name.capitalize() for r in results]
    x = np.arange(len(names))
    width = 0.2
    
    p50_values = [r.latency_50 for r in results]
    p75_values = [r.latency_75 for r in results]
    p90_values = [r.latency_90 for r in results]
    p99_values = [r.latency_99 for r in results]
    
    ax.bar(x - 1.5*width, p50_values, width, label='50th (Median)', 
          color='#60a5fa', alpha=0.9, edgecolor=DARK_TEXT_SECONDARY, linewidth=1.2)
    ax.bar(x - 0.5*width, p75_values, width, label='75th', 
          color='#34d399', alpha=0.9, edgecolor=DARK_TEXT_SECONDARY, linewidth=1.2)
    ax.bar(x + 0.5*width, p90_values, width, label='90th', 
          color='#fbbf24', alpha=0.9, edgecolor=DARK_TEXT_SECONDARY, linewidth=1.2)
    ax.bar(x + 1.5*width, p99_values, width, label='99th', 
          color='#f87171', alpha=0.9, edgecolor=DARK_TEXT_SECONDARY, linewidth=1.2)
    
    ax.set_ylabel('Latency (milliseconds)', fontsize=12, fontweight='bold', color=DARK_TEXT)
    ax.set_title('Latency Percentile Distribution', fontsize=14, fontweight='bold', pad=15, color=DARK_TEXT)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    legend = ax.legend(title='Percentile', fontsize=11, title_fontsize=12, 
                      framealpha=0.95, facecolor=DARK_SURFACE, edgecolor=DARK_TEXT_SECONDARY)
    legend.get_title().set_color(DARK_TEXT)
    for text in legend.get_texts():
        text.set_color(DARK_TEXT)
    ax.grid(axis='y', alpha=0.2, linestyle='--', color=DARK_GRID)
    
    fig.text(0.5, 0.01, 
            'Percentiles show latency experienced by X% of requests (e.g., 99th = 99% of requests were faster than this)', 
            ha='center', fontsize=9, style='italic', color=DARK_TEXT_SECONDARY, wrap=True)
    
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(f'{output_dir}/latency_percentiles.png', dpi=300, bbox_inches='tight', facecolor=DARK_BG)
    print(f"✓ Created {output_dir}/latency_percentiles.png")
    plt.close()

def print_summary(results):
    print("\n" + "="*110)
    print("BENCHMARK RESULTS SUMMARY - Fibonacci Endpoint (n=30)")
    print("="*110)
    print(f"{'Metric':<35} {'Nginx':<18} {'Caddy':<18} {'Traefik':<18} {'HAProxy':<18}")
    print("-"*110)
    
    results_dict = {r.name: r for r in results}
    
    metrics = [
        ('Requests/sec', 'requests_per_sec', '{:.2f}'),
        ('Avg Latency (ms)', 'avg_latency', '{:.2f}'),
        ('50th Percentile (ms)', 'latency_50', '{:.2f}'),
        ('75th Percentile (ms)', 'latency_75', '{:.2f}'),
        ('90th Percentile (ms)', 'latency_90', '{:.2f}'),
        ('99th Percentile (ms)', 'latency_99', '{:.2f}'),
        ('Total Requests', 'total_requests', '{:,}'),
    ]
    
    for metric_name, attr, fmt in metrics:
        nginx_val = fmt.format(getattr(results_dict.get('nginx', BenchmarkResult('nginx')), attr))
        caddy_val = fmt.format(getattr(results_dict.get('caddy', BenchmarkResult('caddy')), attr))
        traefik_val = fmt.format(getattr(results_dict.get('traefik', BenchmarkResult('traefik')), attr))
        haproxy_val = fmt.format(getattr(results_dict.get('haproxy', BenchmarkResult('haproxy')), attr))
        print(f"{metric_name:<35} {nginx_val:<18} {caddy_val:<18} {traefik_val:<18} {haproxy_val:<18}")
    
    if any(r.cpu_timeline for r in results):
        print()
        print("Resource Usage (Average)")
        print("-"*110)
        for r in results:
            if r.cpu_timeline and r.memory_timeline:
                avg_cpu = np.mean(r.cpu_timeline)
                avg_mem = np.mean(r.memory_timeline)
                print(f"{r.name.capitalize():<35} CPU: {avg_cpu:.2f}%{'':<10} Memory: {avg_mem:.2f} MB")
    
    print("="*110)
    
    max_rps = max(results, key=lambda r: r.requests_per_sec)
    min_latency = min(results, key=lambda r: r.avg_latency)
    
    print(f"\n🏆 Highest Throughput: {max_rps.name.upper()} ({max_rps.requests_per_sec:.2f} req/s)")
    print(f"🏆 Lowest Latency: {min_latency.name.upper()} ({min_latency.avg_latency:.2f} ms)")
    
    if any(r.cpu_timeline for r in results):
        min_cpu = min((r for r in results if r.cpu_timeline), 
                     key=lambda r: np.mean(r.cpu_timeline))
        min_mem = min((r for r in results if r.memory_timeline), 
                     key=lambda r: np.mean(r.memory_timeline))
        print(f"🏆 Lowest CPU Usage: {min_cpu.name.upper()} ({np.mean(min_cpu.cpu_timeline):.2f}%)")
        print(f"🏆 Lowest Memory Usage: {min_mem.name.upper()} ({np.mean(min_mem.memory_timeline):.2f} MB)")
    
    print()

def main():
    if len(sys.argv) > 1:
        timestamp = sys.argv[1]
        pattern = f'results/*fibonacci*{timestamp}.txt'
    else:
        pattern = 'results/*fibonacci*.txt'
    
    result_files = glob.glob(pattern)
    
    if not result_files:
        print(f"Error: No result files found matching pattern: {pattern}")
        print("Run ./benchmark.sh first to generate results.")
        sys.exit(1)
    
    if len(sys.argv) == 1:
        timestamps = set()
        for f in result_files:
            match = re.search(r'_(\d{8}_\d{6})\.txt$', f)
            if match:
                timestamps.add(match.group(1))
        
        if timestamps:
            latest_timestamp = max(timestamps)
            result_files = [f for f in result_files if latest_timestamp in f]
    
    results = []
    for filepath in result_files:
        try:
            result = parse_wrk_output(filepath)
            results.append(result)
            print(f"✓ Parsed {filepath}")
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
    
    if not results:
        print("Error: No valid results to analyze")
        sys.exit(1)
    
    print()
    
    results.sort(key=lambda r: r.name)
    
    print_summary(results)
    
    output_dir = 'charts'
    os.makedirs(output_dir, exist_ok=True)
    
    print("Generating charts...")
    create_throughput_chart(results, output_dir)
    create_latency_chart(results, output_dir)
    create_latency_percentiles_chart(results, output_dir)
    
    if any(r.cpu_timeline for r in results):
        create_time_series_chart(results, output_dir)
    else:
        print("Warning: No resource usage metrics found. Skipping resource charts.")
    
    print("\n" + "="*110)
    print("Analysis complete! Check the 'charts' directory for visualizations.")
    print("="*110)
    print("\nGenerated Charts:")
    print("  1. throughput.png              - Requests per second comparison (horizontal bars)")
    print("  2. latency.png                 - Average latency comparison (horizontal bars)")
    print("  3. latency_percentiles.png     - Latency distribution by percentile")
    if any(r.cpu_timeline for r in results):
        print("  4. resource_usage_timeline.png - CPU & memory over time")
    print()

if __name__ == '__main__':
    main()
