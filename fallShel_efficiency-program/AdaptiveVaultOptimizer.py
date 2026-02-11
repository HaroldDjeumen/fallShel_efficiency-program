import json
import os
import numpy as np
from datetime import datetime
from collections import defaultdict

class AdaptiveVaultOptimizer:
    """
    Analyzes performance history and adjusts optimization parameters
    to ensure "with outfits" always beats the initial state
    Supports both adaptive (AI-driven) and manual (user-defined) modes
    """
    
    def __init__(self, vault_name, manual_mode=False):
        self.vault_name = vault_name
        self.config_file = f"{vault_name}_optimizer_config.json"
        self.manual_settings_file = f"{vault_name}_manual_settings.json"
        self.manual_mode = manual_mode
        self.config = self._load_config()
        self.history_file = f"{vault_name}_performance_history.json"
    
    def set_manual_mode(self, enabled):
        """Switch between manual and adaptive modes"""
        self.manual_mode = enabled
        if enabled:
            # Load manual settings if they exist
            self._load_manual_settings()
        else:
            # Reload adaptive config
            self.config = self._load_config()
    
    def _load_manual_settings(self):
        """Load user-defined manual settings"""
        if os.path.exists(self.manual_settings_file):
            try:
                with open(self.manual_settings_file, 'r') as f:
                    manual_settings = json.load(f)
                    # Update config with manual settings
                    self.config.update({
                        'balance_threshold': manual_settings.get('BALANCE_THRESHOLD', 5.0),
                        'max_balance_passes': manual_settings.get('MAX_PASSES', 10),
                        'outfit_strategy': manual_settings.get('OUTFIT_STRATEGY', 'deficit_first'),
                        'swap_aggressiveness': manual_settings.get('SWAP_AGGRESSIVENESS', 1.0),
                        'min_stat_threshold': manual_settings.get('MIN_STAT_THRESHOLD', 5),
                        'enable_cross_stat_balancing': manual_settings.get('ENABLE_CROSS_STAT_BALANCING', True),
                        'room_priorities': manual_settings.get('ROOM_PRIORITIES', {}),
                        'reference_baseline': manual_settings.get('REFERENCE_BASELINE', 'auto')
                    })
                    print(f"✓ Loaded manual settings from {self.manual_settings_file}")
            except Exception as e:
                print(f"⚠ Failed to load manual settings: {e}")
    
    def update_from_manual_settings(self, settings_dict):
        """Update configuration from GUI manual settings"""
        self.config.update({
            'balance_threshold': settings_dict.get('BALANCE_THRESHOLD', 5.0),
            'max_balance_passes': settings_dict.get('MAX_PASSES', 10),
            'outfit_strategy': settings_dict.get('OUTFIT_STRATEGY', 'deficit_first'),
            'swap_aggressiveness': settings_dict.get('SWAP_AGGRESSIVENESS', 1.0),
            'min_stat_threshold': settings_dict.get('MIN_STAT_THRESHOLD', 5),
            'enable_cross_stat_balancing': settings_dict.get('ENABLE_CROSS_STAT_BALANCING', True),
            'room_priorities': settings_dict.get('ROOM_PRIORITIES', {}),
            'reference_baseline': settings_dict.get('REFERENCE_BASELINE', 'auto')
        })
        # Save manual settings
        with open(self.manual_settings_file, 'w') as f:
            json.dump(settings_dict, f, indent=2)
        print(f"✓ Manual settings updated and saved")
    
    def _load_config(self):
        """Load optimizer configuration with adaptive parameters"""
        default_config = {
            'balance_threshold': 5.0,
            'max_balance_passes': 10,
            'outfit_strategy': 'deficit_first',
            'swap_aggressiveness': 1.0,
            'min_stat_threshold': 5,
            'enable_cross_stat_balancing': True,
            'room_priorities': {},
            'reference_baseline': 'auto',  # 'auto', 'initial' or 'before_balancing'
            'learning_rate': 0.1,
            'performance_window': 10,
            'target_improvement': 0.05,
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
        """Save updated configuration (only in adaptive mode)"""
        if not self.manual_mode:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
    
    def apply_adjustments(self, auto_apply=False):
        """Apply suggested adjustments to configuration (only in adaptive mode)"""
        if self.manual_mode:
            print("⚠ Cannot apply adaptive adjustments in Manual Mode")
            return False
        
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
        params = {
            'BALANCE_THRESHOLD': self.config['balance_threshold'],
            'MAX_PASSES': self.config['max_balance_passes'],
            'SWAP_AGGRESSIVENESS': self.config['swap_aggressiveness'],
            'MIN_STAT_THRESHOLD': self.config['min_stat_threshold'],
            'OUTFIT_STRATEGY': self.config['outfit_strategy'],
            'ENABLE_CROSS_STAT_BALANCING': self.config.get('enable_cross_stat_balancing', True),
            'ROOM_PRIORITIES': self.config.get('room_priorities', {}),
            'REFERENCE_BASELINE': self.config.get('reference_baseline', 'auto')
        }
        return params

    def analyze_performance(self):
        """Analyze recent performance history and return metrics and trends"""
        if not os.path.exists(self.history_file):
            return None

        try:
            with open(self.history_file, 'r') as f:
                history = json.load(f)
        except Exception:
            return None

        # Ensure expected keys exist
        for key in ('initial', 'before_balance', 'after_balance', 'with_outfits', 'timestamps'):
            if key not in history or not isinstance(history[key], list):
                return None

        window = min(self.config.get('performance_window', 10), len(history['initial']))
        if window < 2:
            return None

        # Take the last `window` samples
        idx_start = -window
        init_arr = np.array(history['initial'][idx_start:])
        before_arr = np.array(history['before_balance'][idx_start:])
        after_arr = np.array(history['after_balance'][idx_start:])
        with_arr = np.array(history['with_outfits'][idx_start:])

        # Averages
        initial_avg = float(np.mean(init_arr))
        before_balance_avg = float(np.mean(before_arr))
        after_balance_avg = float(np.mean(after_arr))
        with_outfits_avg = float(np.mean(with_arr))

        # Trends (slope per cycle using linear fit)
        x = np.arange(window)
        try:
            initial_trend = float(np.polyfit(x, init_arr, 1)[0])
            with_trend = float(np.polyfit(x, with_arr, 1)[0])
        except Exception:
            # fallback simple diff
            initial_trend = float((init_arr[-1] - init_arr[0]) / max(1, window - 1))
            with_trend = float((with_arr[-1] - with_arr[0]) / max(1, window - 1))

        # Goal checks
        outfit_beats_initial = with_outfits_avg < initial_avg
        outfit_beats_before = with_outfits_avg < before_balance_avg
        outfit_beats_after = with_outfits_avg < after_balance_avg

        analysis = {
            'initial_avg': initial_avg,
            'before_balance_avg': before_balance_avg,
            'after_balance_avg': after_balance_avg,
            'with_outfits_avg': with_outfits_avg,
            'initial_trend': initial_trend,
            'with_outfits_trend': with_trend,
            'outfit_beats_initial': outfit_beats_initial,
            'outfit_beats_before': outfit_beats_before,
            'outfit_beats_after': outfit_beats_after,
            'gap_to_initial': initial_avg - with_outfits_avg,
            'gap_to_before': before_balance_avg - with_outfits_avg,
            'gap_to_after': after_balance_avg - with_outfits_avg,
            'samples': window
        }
        return analysis

    def suggest_adjustments(self):
        """
        Suggest parameter adjustments based on analysis.
        Returns dict: {'analysis': <analysis dict>, 'adjustments': {param: value, ...}}
        """
        analysis = self.analyze_performance()
        if analysis is None:
            return {'analysis': None, 'adjustments': {}}

        adjustments = {}
        lr = float(self.config.get('learning_rate', 0.1))
        target = float(self.config.get('target_improvement', 0.05))

        # If with_outfits is not meaningfully better than initial, increase aggressiveness
        if not analysis['outfit_beats_initial'] or analysis['with_outfits_trend'] > 0:
            # Increase swap aggressiveness slightly (cap at 5.0)
            curr_aggr = float(self.config.get('swap_aggressiveness', 1.0))
            new_aggr = round(min(curr_aggr * (1.0 + lr), 5.0), 2)
            if new_aggr != curr_aggr:
                adjustments['swap_aggressiveness'] = new_aggr

            # Increase max balance passes a bit (cap at 25)
            curr_passes = int(self.config.get('max_balance_passes', 10))
            increment = max(1, int(round(curr_passes * lr)))
            new_passes = min(curr_passes + increment, 25)
            if new_passes != curr_passes:
                adjustments['max_balance_passes'] = new_passes

            # If trend is strongly positive (degrading), nudge balance_threshold up to be more tolerant
            if analysis['with_outfits_trend'] > (target * 10):
                curr_thresh = float(self.config.get('balance_threshold', 5.0))
                new_thresh = round(min(curr_thresh * (1.0 + lr), 20.0), 2)
                adjustments['balance_threshold'] = new_thresh

        # If we are already far better than target, consider reducing aggressiveness to avoid churn
        elif analysis['gap_to_initial'] > (initial_gap := analysis['initial_avg'] * target * 2):
            curr_aggr = float(self.config.get('swap_aggressiveness', 1.0))
            new_aggr = round(max(0.5, curr_aggr * (1.0 - lr / 2)), 2)
            if new_aggr != curr_aggr:
                adjustments['swap_aggressiveness'] = new_aggr

        return {'analysis': analysis, 'adjustments': adjustments}
    
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