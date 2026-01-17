import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

class VaultPerformanceTracker:
    def __init__(self, vault_name):
        self.vault_name = vault_name
        self.data_file = f"{vault_name}_performance_history.json"
        self.history = self._load_history()
    
    def _load_history(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                return {'timestamps': [], 'initial': [], 'before_balance': [], 'after_balance': [], 'with_outfits': []}
        return {'timestamps': [], 'initial': [], 'before_balance': [], 'after_balance': [], 'with_outfits': []}
    
    def _save_history(self):
        """Save performance history to file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def add_cycle_data(self, initial_avg, before_balance_avg, after_balance_avg, with_outfits_avg):
        """
        Add a new cycle's performance data
        
        Args:
            initial_avg: Average production time in initial state
            before_balance_avg: Average before balancing
            after_balance_avg: Average after balancing dwellers
            with_outfits_avg: Average after outfit optimization
        """
        timestamp = datetime.now().isoformat()
        
        self.history['timestamps'].append(timestamp)
        self.history['initial'].append(initial_avg)
        self.history['before_balance'].append(before_balance_avg)
        self.history['after_balance'].append(after_balance_avg)
        self.history['with_outfits'].append(with_outfits_avg)
        
        self._save_history()
        print(f"✓ Recorded cycle data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def generate_performance_graph(self, output_filename=None):
        """Generate a line graph showing performance over time"""
        if not self.history['timestamps']:
            print("No data to plot yet!")
            return
        
        # Convert timestamps to datetime objects
        dates = [datetime.fromisoformat(ts) for ts in self.history['timestamps']]
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # Plot lines with different colors and styles
        ax.plot(dates, self.history['initial'], 
                marker='o', linewidth=2, label='Initial State', 
                color='#ff6b6b', alpha=0.8)
        
        ax.plot(dates, self.history['before_balance'], 
                marker='s', linewidth=2, label='Before Balancing', 
                color='#feca57', alpha=0.8)
        
        ax.plot(dates, self.history['after_balance'], 
                marker='^', linewidth=2, label='After Balancing', 
                color='#48dbfb', alpha=0.8)
        
        ax.plot(dates, self.history['with_outfits'], 
                marker='D', linewidth=2, label='With Outfits', 
                color='#1dd1a1', alpha=0.8)
        
        # Formatting
        ax.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax.set_ylabel('Average Production Time (seconds)', fontsize=12, fontweight='bold')
        ax.set_title(f'{self.vault_name} Performance Over Time', fontsize=14, fontweight='bold')
        
        # Format x-axis to show dates nicely
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        plt.xticks(rotation=45, ha='right')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='upper right', framealpha=0.9, fontsize=10)
        plt.tight_layout()
        
        # Save figure
        if output_filename is None:
            output_filename = f"{self.vault_name}_performance_timeline.png"
        
        plt.savefig(output_filename, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Performance graph saved as: {output_filename}")
        return output_filename
    
    def get_latest_improvement(self):
        """Calculate improvement from initial to final state in latest cycle"""
        if not self.history['timestamps']:
            return None
        
        initial = self.history['initial'][-1]
        final = self.history['with_outfits'][-1]
        improvement_percent = ((initial - final) / initial) * 100
        
        return {
            'initial': initial,
            'final': final,
            'improvement_seconds': round(initial - final, 2),
            'improvement_percent': round(improvement_percent, 2)
        }
    
    def get_summary_stats(self):
        """Get summary statistics across all recorded cycles"""
        if not self.history['timestamps']:
            return None
        
        import statistics
        
        return {
            'total_cycles': len(self.history['timestamps']),
            'avg_initial': round(statistics.mean(self.history['initial']), 2),
            'avg_final': round(statistics.mean(self.history['with_outfits']), 2),
            'best_performance': round(min(self.history['with_outfits']), 2),
            'worst_performance': round(max(self.history['with_outfits']), 2),
            'first_recorded': self.history['timestamps'][0],
            'last_recorded': self.history['timestamps'][-1]
        }
    
    def print_summary(self):
        """Print a summary of vault performance"""
        stats = self.get_summary_stats()
        improvement = self.get_latest_improvement()
        
        if stats is None:
            print("No data recorded yet!")
            return
        
        print("\n" + "="*60)
        print(f"VAULT PERFORMANCE SUMMARY: {self.vault_name}")
        print("="*60)
        print(f"Total Cycles Recorded: {stats['total_cycles']}")
        print(f"First Recorded: {datetime.fromisoformat(stats['first_recorded']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Last Recorded: {datetime.fromisoformat(stats['last_recorded']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nAverage Performance:")
        print(f"  Initial State: {stats['avg_initial']}s")
        print(f"  Optimized State: {stats['avg_final']}s")
        print(f"  Best Performance: {stats['best_performance']}s")
        print(f"  Worst Performance: {stats['worst_performance']}s")
        
        if improvement:
            print(f"\nLatest Cycle Improvement:")
            print(f"  {improvement['initial']}s → {improvement['final']}s")
            print(f"  Improvement: {improvement['improvement_seconds']}s ({improvement['improvement_percent']}%)")
        print("="*60)
    
    def clear_history(self):
        """Clear all recorded history"""
        self.history = {'timestamps': [], 'initial': [], 'before_balance': [], 'after_balance': [], 'with_outfits': []}
        self._save_history()
        print(f"✓ Cleared all history for {self.vault_name}")
