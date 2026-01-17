import json
import os
import numpy as np
from datetime import datetime
from collections import defaultdict

class AdaptiveVaultOptimizer:
    """
    Analyzes performance history and adjusts optimization parameters
    to ensure "with outfits" always beats the initial state
    """
    
    def __init__(self, vault_name):
        self.vault_name = vault_name
        self.config_file = f"{vault_name}_optimizer_config.json"
        self.config = self._load_config()
        self.history_file = f"{vault_name}_performance_history.json"
    
    def _load_config(self):
        """Load optimizer configuration with adaptive parameters"""
        default_config = {
            'balance_threshold': 5.0,  # How close rooms need to be to target
            'max_balance_passes': 10,
            'outfit_strategy': 'deficit_first',  # or 'big_rooms_first'
            'swap_aggressiveness': 1.0,  # How willing to swap dwellers (0.5-2.0)
            'min_stat_threshold': 5,  # Min stat value to consider dweller for room
            'learning_rate': 0.1,  # How fast to adjust parameters
            'performance_window': 10,  # Number of cycles to analyze
            'target_improvement': 0.05,  # 5% improvement target
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except:
                pass
        
        return default_config
    
    def _save_config(self):
        """Save updated configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def analyze_performance(self):
        """Analyze recent performance and identify issues"""
        if not os.path.exists(self.history_file):
            return None
        
        with open(self.history_file, 'r') as f:
            history = json.load(f)
        
        if len(history['timestamps']) < 2:
            return None
        
        # Get recent window
        window = self.config['performance_window']
        initial = history['initial'][-window:]
        before_balance = history['before_balance'][-window:]
        after_balance = history['after_balance'][-window:]
        with_outfits = history['with_outfits'][-window:]
        
        analysis = {
            'initial_avg': np.mean(initial),
            'before_balance_avg': np.mean(before_balance),
            'after_balance_avg': np.mean(after_balance),
            'with_outfits_avg': np.mean(with_outfits),
            'initial_trend': self._calculate_trend(initial),
            'with_outfits_trend': self._calculate_trend(with_outfits),
        }
        
        # Check if goals are met
        analysis['outfit_beats_initial'] = analysis['with_outfits_avg'] < analysis['initial_avg']
        analysis['outfit_beats_before'] = analysis['with_outfits_avg'] < analysis['before_balance_avg']
        analysis['outfit_beats_after'] = analysis['with_outfits_avg'] < analysis['after_balance_avg']
        
        # Calculate gaps
        analysis['gap_to_initial'] = analysis['with_outfits_avg'] - analysis['initial_avg']
        analysis['gap_to_before'] = analysis['with_outfits_avg'] - analysis['before_balance_avg']
        analysis['gap_to_after'] = analysis['with_outfits_avg'] - analysis['after_balance_avg']
        
        return analysis
    
    def _calculate_trend(self, values):
        """Calculate trend direction (positive = getting worse)"""
        if len(values) < 2:
            return 0
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        return slope
    
    def suggest_adjustments(self):
        """Analyze performance and suggest parameter adjustments"""
        analysis = self.analyze_performance()
        
        if analysis is None:
            print("Not enough data to analyze yet")
            return None
        
        suggestions = {
            'issues': [],
            'adjustments': {},
            'reasoning': []
        }
        
        print("\n" + "="*60)
        print("ADAPTIVE OPTIMIZER ANALYSIS")
        print("="*60)
        
        # Issue 1: Outfit optimization not beating initial state
        if not analysis['outfit_beats_initial']:
            gap = analysis['gap_to_initial']
            suggestions['issues'].append(f"With Outfits ({analysis['with_outfits_avg']:.1f}s) NOT beating Initial ({analysis['initial_avg']:.1f}s) by {gap:.1f}s")
            suggestions['reasoning'].append("Need more aggressive optimization")
            
            # Increase swap aggressiveness
            new_aggression = min(2.0, self.config['swap_aggressiveness'] * 1.2)
            suggestions['adjustments']['swap_aggressiveness'] = new_aggression
            
            # Tighten balance threshold
            new_threshold = max(2.0, self.config['balance_threshold'] * 0.8)
            suggestions['adjustments']['balance_threshold'] = new_threshold
            
            # More balance passes
            new_passes = min(20, self.config['max_balance_passes'] + 3)
            suggestions['adjustments']['max_balance_passes'] = new_passes
        
        # Issue 2: Before/After balance not improving over initial
        if not analysis['outfit_beats_before']:
            gap = analysis['gap_to_before']
            suggestions['issues'].append(f"With Outfits not beating Before Balance by {gap:.1f}s")
            suggestions['reasoning'].append("Algorithm placement worse than initial - need better dweller assignment")
            
            # Change outfit strategy
            if self.config['outfit_strategy'] == 'deficit_first':
                suggestions['adjustments']['outfit_strategy'] = 'hybrid'
            
            # Increase min stat threshold (only assign good dwellers)
            new_min = min(8, self.config['min_stat_threshold'] + 1)
            suggestions['adjustments']['min_stat_threshold'] = new_min
        
        # Issue 3: Performance getting worse over time
        if analysis['with_outfits_trend'] > 0.1:  # Getting slower
            suggestions['issues'].append(f"With Outfits performance degrading (trend: +{analysis['with_outfits_trend']:.2f}s per cycle)")
            suggestions['reasoning'].append("Need to adapt to changing vault state")
            
            # Be more aggressive with swaps
            new_aggression = min(2.0, self.config['swap_aggressiveness'] * 1.3)
            suggestions['adjustments']['swap_aggressiveness'] = new_aggression
        
        # Success case: Everything working well
        if (analysis['outfit_beats_initial'] and 
            analysis['outfit_beats_before'] and 
            analysis['outfit_beats_after']):
            improvement = ((analysis['initial_avg'] - analysis['with_outfits_avg']) / 
                          analysis['initial_avg']) * 100
            print(f"✓ Optimization working well! {improvement:.1f}% improvement")
            print(f"  Initial: {analysis['initial_avg']:.1f}s")
            print(f"  With Outfits: {analysis['with_outfits_avg']:.1f}s")
            
            # Fine-tune for even better performance
            if improvement < 10:  # Less than 10% improvement
                suggestions['reasoning'].append("Good performance, but can do better")
                new_threshold = max(2.0, self.config['balance_threshold'] * 0.9)
                suggestions['adjustments']['balance_threshold'] = new_threshold
        
        # Print suggestions
        if suggestions['issues']:
            print("\n⚠ Issues Detected:")
            for issue in suggestions['issues']:
                print(f"  - {issue}")
            
            print("\n💡 Reasoning:")
            for reason in suggestions['reasoning']:
                print(f"  - {reason}")
            
            print("\n🔧 Suggested Adjustments:")
            for param, value in suggestions['adjustments'].items():
                old_value = self.config[param]
                print(f"  {param}: {old_value} → {value}")
        
        return suggestions
    
    def apply_adjustments(self, auto_apply=False):
        """Apply suggested adjustments to configuration"""
        suggestions = self.suggest_adjustments()
        
        if suggestions is None or not suggestions['adjustments']:
            return False
        
        if not auto_apply:
            print("\nApply these adjustments? (y/n): ", end="")
            response = input().strip().lower()
            if response != 'y':
                print("Adjustments not applied")
                return False
        
        # Apply adjustments
        for param, value in suggestions['adjustments'].items():
            self.config[param] = value
        
        self._save_config()
        print("\n✓ Adjustments applied and saved!")
        return True
    
    def get_optimization_params(self):
        """Get current optimization parameters for use in placementCalc"""
        return {
            'BALANCE_THRESHOLD': self.config['balance_threshold'],
            'MAX_PASSES': self.config['max_balance_passes'],
            'SWAP_AGGRESSIVENESS': self.config['swap_aggressiveness'],
            'MIN_STAT_THRESHOLD': self.config['min_stat_threshold'],
            'OUTFIT_STRATEGY': self.config['outfit_strategy']
        }
    
    def generate_recommendation_report(self):
        """Generate a detailed report with recommendations"""
        analysis = self.analyze_performance()
        
        if analysis is None:
            return
        
        print("\n" + "="*60)
        print("OPTIMIZATION RECOMMENDATION REPORT")
        print("="*60)
        
        print("\nCurrent Performance (Last 10 cycles average):")
        print(f"  Initial State:      {analysis['initial_avg']:.2f}s")
        print(f"  Before Balancing:   {analysis['before_balance_avg']:.2f}s")
        print(f"  After Balancing:    {analysis['after_balance_avg']:.2f}s")
        print(f"  With Outfits:       {analysis['with_outfits_avg']:.2f}s")
        
        print("\nPerformance Trends:")
        print(f"  Initial:      {'📉 Improving' if analysis['initial_trend'] < 0 else '📈 Degrading'} ({analysis['initial_trend']:.3f}s/cycle)")
        print(f"  With Outfits: {'📉 Improving' if analysis['with_outfits_trend'] < 0 else '📈 Degrading'} ({analysis['with_outfits_trend']:.3f}s/cycle)")
        
        print("\nGoal Achievement:")
        print(f"  {'✓' if analysis['outfit_beats_initial'] else '✗'} With Outfits beats Initial: {analysis['gap_to_initial']:.2f}s gap")
        print(f"  {'✓' if analysis['outfit_beats_before'] else '✗'} With Outfits beats Before Balance: {analysis['gap_to_before']:.2f}s gap")
        print(f"  {'✓' if analysis['outfit_beats_after'] else '✗'} With Outfits beats After Balance: {analysis['gap_to_after']:.2f}s gap")
        
        print("\nCurrent Configuration:")
        for param, value in self.config.items():
            print(f"  {param}: {value}")
        
        print("="*60) 