import sys
import os
import json
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QTextEdit, 
                               QLineEdit, QGroupBox, QListWidget, QTabWidget,
                               QProgressBar, QScrollArea, QFrame, QSplitter, QMessageBox,
                               QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QFormLayout, QRadioButton, QFileDialog)
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor, QPixmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from placementCalc import NULL
from placementCalc import BalancingConfig
from outfit_manager import OutfitDatabaseManager
from AdaptiveVaultOptimizer import AdaptiveVaultOptimizer
from version import __version__ as APP_VERSION
import updater
from vault_map_tab import VaultMapTab
from vault_map_tab import RoomCell



vault_design = []

# Thread for running optimization cycles
class OptimizationThread(QThread):
    cycle_complete = Signal(int, dict)  # cycle_number, stats
    error_occurred = Signal(str)
    # accept any Python object (str path, dict, or list) from the worker
    dweller_suggestions = Signal(dict)
    missing_outfits_found = Signal(list)  # Signal for missing outfits
    vault_design_ready = Signal(list)     # <-- new signal to send vault design to GUI
    
    def __init__(self, vault_name, outfit_list, optimizer_params=None):
        super().__init__()
        self.vault_name = vault_name
        self.outfit_list = outfit_list
        self.optimizer_params = optimizer_params
        self.running = True
        self.cycle_count = 0
        
    def run(self):
        import time
        # Import your modules
        import sav_fetcher
        import TableSorter
        import virtualvaultmap
        import placementCalc
        from VaultPerformanceTracker import VaultPerformanceTracker
        from AdaptiveVaultOptimizer import AdaptiveVaultOptimizer
        
        optimizer = AdaptiveVaultOptimizer(self.vault_name)
        
        while self.running:
            try:
                self.cycle_count += 1
                
                # Use manual params if provided, otherwise get from optimizer
                if self.optimizer_params:
                    optimizer_params = self.optimizer_params
                else:
                    optimizer_params = optimizer.get_optimization_params()
                
                # Run cycle
                json_path = sav_fetcher.run(self.vault_name)
                outfitlist = TableSorter.run(json_path)
               

                outfit_manager = OutfitDatabaseManager()
                missing = outfit_manager.check_missing_outfits(outfitlist)
                
                if missing and self.cycle_count in range(1, 100):  # Only check on first cycle
                    self.missing_outfits_found.emit(missing)
                    # Pause thread until user handles missing outfits
                    while missing:
                        time.sleep(0.5)
                        # Recheck to see if they've been added
                        missing = outfit_manager.check_missing_outfits(outfitlist)
                        if not self.running:
                            return
                
                virtualvaultmap.run(json_path)
                self.vault_design = virtualvaultmap.run(json_path)
                # Emit the design so the main thread can update the VaultMapTab
                self.vault_design_ready.emit(self.vault_design)

                # Update vault map widget if provided (schedule on main thread)
                if getattr(self, "vault_widget", None) is not None:
                    try:
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(0, lambda d=self.vault_design: self.vault_widget.set_vault_design(d))
                    except Exception:
                        # Fallback: try direct call (not recommended but safe as last resort)
                        try:
                            self.vault_widget.set_vault_design(self.vault_design)
                        except Exception:
                            pass
                
                # Capture suggestions or results file from placementCalc
                suggestions = None
                suggestion_path = placementCalc.run(
                    json_path, outfitlist, self.vault_name, optimizer_params
                )

                try:
                    with open(suggestion_path, 'r') as file:
                        suggestions = json.load(file)  # <-- important
                except FileNotFoundError:
                    print(f"Error: The file '{suggestion_path}' was not found.")
                except IOError as e:
                    print(e)
                
                # Emit whatever placementCalc returned (path, dict, or list)
                if suggestions is not None:
                    self.dweller_suggestions.emit(suggestions)
                
                # Get performance stats
                tracker = VaultPerformanceTracker(self.vault_name)
                stats = {
                    'cycle': self.cycle_count,
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'params': optimizer_params
                }
                
                self.cycle_complete.emit(self.cycle_count, stats)
                
                # Every 5 cycles, run adaptive analysis (only if not using manual params)
                if not self.optimizer_params and self.cycle_count % 2 == 0 and self.cycle_count >= 2:
                    optimizer.apply_adjustments(auto_apply=True)
                
                # Wait 60 seconds
                for _ in range(60):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.error_occurred.emit(str(e))
                break
    
    def stop(self):
        self.running = False





class ProductionBarChart(FigureCanvas):
    """Bar chart showing current cycle's room production times"""
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(10, 4), facecolor='#1a1a1a')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2a2a2a')
        self.ax.tick_params(colors='#00ff00', which='both')
        self.ax.spines['bottom'].set_color('#00ff00')
        self.ax.spines['top'].set_color('#00ff00')
        self.ax.spines['left'].set_color('#00ff00')
        self.ax.spines['right'].set_color('#00ff00')
        
        self.setup_plot()
    
    def setup_plot(self):
        self.ax.clear()
        self.ax.set_facecolor('#2a2a2a')
        self.ax.set_xlabel('Room', color='#00ff00', fontsize=10)
        self.ax.set_ylabel('Production Time (s)', color='#00ff00', fontsize=10)
        self.ax.set_title('Room Production Times: Initial → Balanced → Optimized with Outfits', 
                         color='#ffcc00', fontsize=12, fontweight='bold')
        self.ax.grid(axis='y', alpha=0.2, color='#00ff00')
        self.draw()
    
    def update_plot(self, results_file):
        """Load latest cycle production data and plot bars"""
        if not results_file or not os.path.exists(results_file):
            return
        
        import json
        with open(results_file, 'r') as f:
            data = json.load(f)
        
        # Get room assignments and production times
        rooms = []
        initial_times = []
        before_balance_times = []
        after_balance_times = []
        with_outfits_times = []
        
        # Sort rooms by type and number
        sorted_rooms = sorted(data['room_assignments'].items(), 
                            key=lambda x: (x[1]['room_type'], x[1]['number']))
        
        for room_id, room_data in sorted_rooms:
            # Skip training rooms (including Classroom)
            if room_data['room_type'] in ['Gym', 'Armory', 'Dojo', 'Classroom']:
                continue
            
            room_label = f"{room_data['room_type']}-{room_data['level']}-{room_data['size']}-{room_data['number']}"
            rooms.append(room_label)
            
            # Get production times (you'll need to add these to your JSON)
            initial_times.append(room_data.get('initial_time', 0))
            before_balance_times.append(room_data.get('before_balance_time', 0))
            after_balance_times.append(room_data.get('after_balance_time', 0))
            with_outfits_times.append(room_data.get('production_time', 0))
        
        if not rooms:
            return
        
        import numpy as np
        
        self.ax.clear()
        self.ax.set_facecolor('#2a2a2a')
        
        x = np.arange(len(rooms))
        width = 0.2
        
        # Plot bars
        self.ax.bar(x - 1.5*width, initial_times, width=width, 
                   label='Initial', color='#ff6b6b', alpha=0.9)
        self.ax.bar(x - 0.5*width, before_balance_times, width=width, 
                   label='Before Balancing', color='#feca57', alpha=0.9)
        self.ax.bar(x + 0.5*width, after_balance_times, width=width, 
                   label='After Balancing', color='#48dbfb', alpha=0.9)
        self.ax.bar(x + 1.5*width, with_outfits_times, width=width, 
                   label='With Outfits', color='#1dd1a1', alpha=0.9)
        
        self.ax.set_xlabel('Room', color='#00ff00', fontsize=10)
        self.ax.set_ylabel('Production Time (s)', color='#00ff00', fontsize=10)
        self.ax.set_title('Room Production Times: Initial → Balanced → Optimized with Outfits', 
                         color='#ffcc00', fontsize=12, fontweight='bold')
        self.ax.set_xticks(x)
        self.ax.set_xticklabels(rooms, rotation=45, ha='right', fontsize=8)
        self.ax.legend(facecolor='#2a2a2a', edgecolor='#00ff00', labelcolor='#00ff00', fontsize=9)
        self.ax.grid(axis='y', alpha=0.2, color='#00ff00')
        self.ax.tick_params(colors='#00ff00', which='both')
        
        self.fig.tight_layout()
        self.draw()


class PerformanceChart(FigureCanvas):
    """Timeline chart showing performance over time (datetime on x-axis)"""
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(10, 3.5), facecolor='#1a1a1a')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2a2a2a')
        self.ax.tick_params(colors='#00ff00', which='both')
        self.ax.spines['bottom'].set_color('#00ff00')
        self.ax.spines['top'].set_color('#00ff00')
        self.ax.spines['left'].set_color('#00ff00')
        self.ax.spines['right'].set_color('#00ff00')
        
        self.setup_plot()
    
    def setup_plot(self):
        self.ax.clear()
        self.ax.set_facecolor('#2a2a2a')
        self.ax.set_xlabel('Time', color='#00ff00', fontsize=10)
        self.ax.set_ylabel('Average Production Time (s)', color='#00ff00', fontsize=10)
        self.ax.set_title('Vault Performance Over Time', color='#ffcc00', fontsize=12, fontweight='bold')
        self.ax.grid(True, alpha=0.2, color='#00ff00')
        self.draw()
    
    def update_plot(self, vault_name):
        """Load data from performance history and update plot with datetime x-axis"""
        import json
        from datetime import datetime
        import matplotlib.dates as mdates
        
        history_file = f"{vault_name}_performance_history.json"
        
        if not os.path.exists(history_file):
            return
        
        with open(history_file, 'r') as f:
            history = json.load(f)
        
        if not history['timestamps']:
            return
                        
        # Convert timestamps to datetime objects
        dates = [datetime.fromisoformat(ts) for ts in history['timestamps']]
        
        self.ax.clear()
        self.ax.set_facecolor('#2a2a2a')
        
        # Plot lines with datetime x-axis
        self.ax.plot(dates, history['initial'], 
                    marker='o', color='#ff6b6b', linewidth=2, markersize=6, label='Initial State')
        self.ax.plot(dates, history['before_balance'], 
                    marker='s', color='#feca57', linewidth=2, markersize=6, label='Before Balancing')
        self.ax.plot(dates, history['after_balance'], 
                    marker='^', color='#48dbfb', linewidth=2, markersize=6, label='After Balancing')
        self.ax.plot(dates, history['with_outfits'], 
                    marker='D', color='#1dd1a1', linewidth=2, markersize=6, label='With Outfits')
        
        # Format x-axis to show time
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        self.fig.autofmt_xdate()  # Rotate date labels
        
        self.ax.set_xlabel('Time', color='#00ff00', fontsize=10)
        self.ax.set_ylabel('Average Production Time (seconds)', color='#00ff00', fontsize=10)
        self.ax.set_title('Vault Performance Over Time', color='#ffcc00', fontsize=12, fontweight='bold')
        self.ax.legend(facecolor='#2a2a2a', edgecolor='#00ff00', labelcolor='#00ff00', fontsize=9)
        self.ax.grid(True, alpha=0.3, color='#00ff00')
        self.ax.tick_params(colors='#00ff00', which='both')
        
        self.fig.tight_layout()
        self.draw()


class UpdateCheckThread(QThread):
    finished_signal = Signal(dict)
    def __init__(self, current_version: str, repo: str, asset_match: str = "win"):
        super().__init__()
        self.current_version = current_version
        self.repo = repo
        self.asset_match = asset_match
    def run(self):
        try:
            result = updater.check_for_update(self.current_version, self.repo, asset_name_match=self.asset_match)
        except Exception as e:
            result = {'update_available': False, 'latest_version': None, 'downloaded_installer': None, 'error': str(e)}
        self.finished_signal.emit(result)
    

class FalloutShelterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fallout Shelter - Vault Optimizer")
        self.setGeometry(100, 100, 1400, 900)
        
        # Apply Fallout theme
        self.apply_fallout_theme()
        
        # State
        self.optimization_thread = None
        self.vault_name = None
        self.is_running = False
        self.outfit_manager = OutfitDatabaseManager()
        self.manual_mode = False  
        
        # Setup UI
        self.setup_ui()
        
        # Timer for updating chart
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        
    def apply_fallout_theme(self):
        """Apply Fallout-inspired color scheme"""
        palette = QPalette()
        
        # Background colors (dark grey/black)
        palette.setColor(QPalette.Window, QColor(26, 26, 26))
        palette.setColor(QPalette.WindowText, QColor(0, 255, 0))
        palette.setColor(QPalette.Base, QColor(42, 42, 42))
        palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
        palette.setColor(QPalette.Text, QColor(0, 255, 0))
        palette.setColor(QPalette.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ButtonText, QColor(255, 204, 0))
        palette.setColor(QPalette.Highlight, QColor(255, 204, 0))
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        
        self.setPalette(palette)
        
        # Set stylesheet for additional styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QGroupBox {
                border: 2px solid #00ff00;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #ffcc00;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #333333;
                border: 2px solid #00ff00;
                border-radius: 5px;
                padding: 8px;
                color: #ffcc00;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #00ff00;
                color: #000000;
            }
            QPushButton:pressed {
                background-color: #ffcc00;
                border-color: #ffcc00;
            }
            QPushButton:disabled {
                background-color: #222222;
                border-color: #555555;
                color: #555555;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #2a2a2a;
                border: 2px solid #00ff00;
                border-radius: 3px;
                padding: 5px;
                color: #00ff00;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #00ff00;
                margin-right: 5px;
            }
            QTextEdit, QListWidget {
                background-color: #2a2a2a;
                border: 2px solid #00ff00;
                border-radius: 3px;
                color: #00ff00;
                font-family: 'Courier New';
                font-size: 10px;
            }
            QLabel {
                color: #00ff00;
                font-size: 11px;
            }
            QCheckBox {
                color: #00ff00;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #00ff00;
                border-radius: 3px;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background-color: #00ff00;
                image: none;
            }
            QProgressBar {
                border: 2px solid #00ff00;
                border-radius: 5px;
                text-align: center;
                background-color: #2a2a2a;
                color: #ffcc00;
            }
            QProgressBar::chunk {
                background-color: #00ff00;
            }
            QTabWidget::pane {
                border: 2px solid #00ff00;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #333333;
                border: 2px solid #00ff00;
                padding: 8px 20px;
                color: #ffcc00;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #00ff00;
                color: #000000;
            }
            QScrollBar:vertical {
                border: 1px solid #00ff00;
                background: #2a2a2a;
                width: 15px;
            }
            QScrollBar::handle:vertical {
                background: #00ff00;
                min-height: 20px;
            }
        """)
    
    def setup_ui(self):
        """Setup the main UI layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Controls and Info
        left_panel = self.create_left_panel()
        
        # Right panel - Charts and Suggestions
        right_panel = self.create_right_panel()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
    
    def create_left_panel(self):
        """Create left control panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("VAULT-TEC OPTIMIZER")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffcc00; padding: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Vault selection
        vault_group = QGroupBox("Vault Configuration")
        vault_layout = QVBoxLayout()
        
        vault_input_layout = QHBoxLayout()
        vault_input_layout.addWidget(QLabel("Vault Number:"))
        self.vault_input = QLineEdit()
        self.vault_input.setPlaceholderText("Enter number ")
        vault_input_layout.addWidget(self.vault_input)
        vault_layout.addLayout(vault_input_layout)
        
        vault_group.setLayout(vault_layout)
        layout.addWidget(vault_group)
        
        # Control buttons
        control_group = QGroupBox("Control Panel")
        control_layout = QVBoxLayout()
        
        self.start_btn = QPushButton("▶ START OPTIMIZATION")
        self.start_btn.clicked.connect(self.start_optimization)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ STOP OPTIMIZATION")
        self.stop_btn.clicked.connect(self.stop_optimization)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        # Add check for updates button
        self.check_updates_btn = QPushButton("⬆️ CHECK FOR UPDATES")
        self.check_updates_btn.clicked.connect(self.check_updates_action)
        control_layout.addWidget(self.check_updates_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Status display
        status_group = QGroupBox("System Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Status: IDLE")
        self.status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffcc00;")
        status_layout.addWidget(self.status_label)
        
        self.cycle_label = QLabel("Cycles Completed: 0")
        status_layout.addWidget(self.cycle_label)
        
        # Countdown timer label
        self.countdown_label = QLabel("Next cycle in: --")
        self.countdown_label.setStyleSheet("color: #48dbfb; font-size: 11px;")
        status_layout.addWidget(self.countdown_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)  # Changed from 60 to 100 for percentage
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")  # Show percentage
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Log console
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(200)
        log_layout.addWidget(self.log_console)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Fallout tips
        tips_group = QGroupBox("Vault-Tec Tips")
        tips_layout = QVBoxLayout()
        
        self.tips_list = QListWidget()
        self.load_fallout_tips()
        tips_layout.addWidget(self.tips_list)
        
        tips_group.setLayout(tips_layout)
        layout.addWidget(tips_group)
        
        layout.addStretch()
        return panel
    
    def create_settings_tab(self):
        """Create comprehensive settings tab with all configurable parameters"""
        settings_widget = QWidget()
        main_layout = QVBoxLayout(settings_widget)
        
        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Header
        header = QLabel("⚙️ OPTIMIZATION SETTINGS")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffcc00; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        scroll_layout.addWidget(header)
        
        # Mode selection
        mode_group = QGroupBox("Optimization Mode")
        mode_layout = QVBoxLayout()
        
        self.auto_mode_radio = QRadioButton("Adaptive Mode (AI adjusts settings automatically)")
        self.auto_mode_radio.setChecked(True)
        self.auto_mode_radio.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.auto_mode_radio)
        
        self.manual_mode_radio = QRadioButton("Manual Mode (Use settings below)")
        self.manual_mode_radio.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.manual_mode_radio)
        
        mode_info = QLabel("In Adaptive Mode, the optimizer will automatically adjust settings based on performance.")
        mode_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        mode_info.setWordWrap(True)
        mode_layout.addWidget(mode_info)
        
        mode_group.setLayout(mode_layout)
        scroll_layout.addWidget(mode_group)
        
        # Balancing Parameters
        balance_group = QGroupBox("Balancing Parameters")
        balance_layout = QFormLayout()
        
        # Balance threshold
        self.balance_threshold_spin = QDoubleSpinBox()
        self.balance_threshold_spin.setRange(1.0, 20.0)
        self.balance_threshold_spin.setValue(5.0)
        self.balance_threshold_spin.setSingleStep(0.5)
        self.balance_threshold_spin.setSuffix(" seconds")
        balance_layout.addRow("Balance Threshold:", self.balance_threshold_spin)
        
        threshold_info = QLabel("How close room times need to be to target (lower = more aggressive balancing)")
        threshold_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        threshold_info.setWordWrap(True)
        balance_layout.addRow("", threshold_info)
        
        # Max balance passes
        self.max_passes_spin = QSpinBox()
        self.max_passes_spin.setRange(1, 25)
        self.max_passes_spin.setValue(10)
        balance_layout.addRow("Max Balance Passes:", self.max_passes_spin)
        
        passes_info = QLabel("Maximum number of balancing iterations (more passes = more thorough)")
        passes_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        passes_info.setWordWrap(True)
        balance_layout.addRow("", passes_info)
        
        # Cross-stat balancing
        self.cross_stat_check = QRadioButton("Enable Cross-Stat Balancing")
        self.cross_stat_check.setChecked(True)
        balance_layout.addRow("", self.cross_stat_check)
        
        cross_stat_info = QLabel("Allow dweller swaps between different room types (e.g., Power ↔ Water)")
        cross_stat_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        cross_stat_info.setWordWrap(True)
        balance_layout.addRow("", cross_stat_info)
        
        # Reference Baseline Selection
        ref_label = QLabel("Reference Baseline:")
        ref_label.setStyleSheet("color: #ffcc00; font-weight: bold;")
        
        self.ref_baseline_combo = QComboBox()
        self.ref_baseline_combo.addItems(["Auto (Best Performance)", "Initial State", "Before Balancing"])
        self.ref_baseline_combo.setCurrentText("Auto (Best Performance)")
        balance_layout.addRow(ref_label, self.ref_baseline_combo)
        
        ref_info = QLabel("Choose which state to use as reference for balancing optimization")
        ref_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        ref_info.setWordWrap(True)
        balance_layout.addRow("", ref_info)
        
        balance_group.setLayout(balance_layout)
        scroll_layout.addWidget(balance_group)
        
        # Dweller Assignment Parameters
        dweller_group = QGroupBox("Dweller Assignment")
        dweller_layout = QFormLayout()
        
        # Swap aggressiveness
        self.swap_aggression_spin = QDoubleSpinBox()
        self.swap_aggression_spin.setRange(0.5, 5.0)
        self.swap_aggression_spin.setValue(1.0)
        self.swap_aggression_spin.setSingleStep(0.1)
        dweller_layout.addRow("Swap Aggressiveness:", self.swap_aggression_spin)
        
        aggression_info = QLabel("How willing to move dwellers (0.5=conservative, 5.0=very aggressive)")
        aggression_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        aggression_info.setWordWrap(True)
        dweller_layout.addRow("", aggression_info)
        
        # Min stat threshold
        self.min_stat_spin = QSpinBox()
        self.min_stat_spin.setRange(0, 10)
        self.min_stat_spin.setValue(5)
        dweller_layout.addRow("Min Stat Threshold:", self.min_stat_spin)
        
        min_stat_info = QLabel("Minimum stat value for dweller assignment (0=allow all, 10=only best)")
        min_stat_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        min_stat_info.setWordWrap(True)
        dweller_layout.addRow("", min_stat_info)
        
        dweller_group.setLayout(dweller_layout)
        scroll_layout.addWidget(dweller_group)
        
        # Outfit Strategy
        outfit_group = QGroupBox("Outfit Assignment Strategy")
        outfit_layout = QFormLayout()
        
        self.outfit_strategy_combo = QComboBox()
        self.outfit_strategy_combo.addItems([
            "deficit_first", 
            "big_rooms_first", 
            "hybrid",
            "efficiency_first"
        ])
        outfit_layout.addRow("Strategy:", self.outfit_strategy_combo)
        
        strategy_info = QLabel(
            "deficit_first: Prioritize rooms needing most help\n"
            "big_rooms_first: Prioritize high-level/merged rooms\n"
            "hybrid: Balance between deficit and room size\n"
            "efficiency_first: Maximize outfit stat efficiency"
        )
        strategy_info.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        strategy_info.setWordWrap(True)
        outfit_layout.addRow("", strategy_info)
        
        outfit_group.setLayout(outfit_layout)
        scroll_layout.addWidget(outfit_group)
        
        # Room Priorities
        priority_group = QGroupBox("Room Type Priorities")
        priority_layout = QFormLayout()
        
        priority_info = QLabel("Lower number = higher priority (1=highest, 10=lowest)")
        priority_info.setStyleSheet("color: #ffcc00; font-size: 12px; font-weight: bold;")
        priority_info.setWordWrap(True)
        priority_layout.addRow("", priority_info)
        
        self.priority_spins = {}
        room_types = ['Medbay', 'Power', 'Water', 'Food']
        default_priorities = {'Medbay': 1, 'Power': 2, 'Water': 3, 'Food': 4}
        
        for room_type in room_types:
            spin = QSpinBox()
            spin.setRange(1, 10)
            spin.setValue(default_priorities.get(room_type, 5))
            self.priority_spins[room_type] = spin
            priority_layout.addRow(f"{room_type}:", spin)
        
        priority_group.setLayout(priority_layout)
        scroll_layout.addWidget(priority_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.save_settings_btn = QPushButton("💾 SAVE SETTINGS")
        self.save_settings_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_settings_btn)
        
        self.load_settings_btn = QPushButton("📂 LOAD SETTINGS")
        self.load_settings_btn.clicked.connect(self.load_settings)
        button_layout.addWidget(self.load_settings_btn)
        
        self.reset_settings_btn = QPushButton("🔄 RESET TO DEFAULTS")
        self.reset_settings_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_settings_btn)
        
        scroll_layout.addLayout(button_layout)
        
        # Status message
        self.settings_status = QLabel("")
        self.settings_status.setStyleSheet("color: #1dd1a1; font-size: 11px; font-weight: bold;")
        self.settings_status.setAlignment(Qt.AlignCenter)
        scroll_layout.addWidget(self.settings_status)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)       # <-- ensure the scroll area is added to the tab
        self.disable_settings_controls()
        return settings_widget
    
    def on_mode_changed(self):
        """Handle mode toggle between adaptive and manual"""
        if self.auto_mode_radio.isChecked():
            self.manual_mode = False
            self.manual_mode_radio.setChecked(False)
            self.disable_settings_controls()
            self.log("Switched to Adaptive Mode - AI will adjust settings", "#48dbfb")
            if hasattr(self, 'optimizer') and self.optimizer:
                self.optimizer.set_manual_mode(False)
        elif self.manual_mode_radio.isChecked():
            self.manual_mode = True
            self.auto_mode_radio.setChecked(False)
            self.enable_settings_controls()
            self.log("Switched to Manual Mode - Using custom settings", "#ffcc00")
            if hasattr(self, 'optimizer') and self.optimizer:
                self.optimizer.set_manual_mode(True)
                current_settings = self.get_current_settings()
                self.optimizer.update_from_manual_settings(current_settings)

    def disable_settings_controls(self):
        """Disable all settings controls (used in Adaptive Mode)"""
        disabled_tooltip = "Switch to Manual Mode to edit this setting"
        
        self.balance_threshold_spin.setEnabled(False)
        self.balance_threshold_spin.setToolTip(disabled_tooltip)
        
        self.max_passes_spin.setEnabled(False)
        self.max_passes_spin.setToolTip(disabled_tooltip)
        
        self.cross_stat_check.setEnabled(False)
        self.cross_stat_check.setToolTip(disabled_tooltip)
        
        self.swap_aggression_spin.setEnabled(False)
        self.swap_aggression_spin.setToolTip(disabled_tooltip)
        
        self.min_stat_spin.setEnabled(False)
        self.min_stat_spin.setToolTip(disabled_tooltip)
        
        self.outfit_strategy_combo.setEnabled(False)
        self.outfit_strategy_combo.setToolTip(disabled_tooltip)
        
        for spin in self.priority_spins.values():
            spin.setEnabled(False)
            spin.setToolTip(disabled_tooltip)
        
        self.save_settings_btn.setEnabled(False)
        self.save_settings_btn.setToolTip(disabled_tooltip)
        
        self.reset_settings_btn.setEnabled(False)
        self.reset_settings_btn.setToolTip(disabled_tooltip)
    
    def enable_settings_controls(self):
        """Enable all settings controls (used in Manual Mode)"""
        self.balance_threshold_spin.setEnabled(True)
        self.balance_threshold_spin.setToolTip("")
        
        self.max_passes_spin.setEnabled(True)
        self.max_passes_spin.setToolTip("")
        
        self.cross_stat_check.setEnabled(True)
        self.cross_stat_check.setToolTip("")
        
        self.swap_aggression_spin.setEnabled(True)
        self.swap_aggression_spin.setToolTip("")
        
        self.min_stat_spin.setEnabled(True)
        self.min_stat_spin.setToolTip("")
        
        self.outfit_strategy_combo.setEnabled(True)
        self.outfit_strategy_combo.setToolTip("")
        
        for spin in self.priority_spins.values():
            spin.setEnabled(True)
            spin.setToolTip("")
        
        self.save_settings_btn.setEnabled(True)
        self.save_settings_btn.setToolTip("")
        
        self.reset_settings_btn.setEnabled(True)
        self.reset_settings_btn.setToolTip("")
    
    def get_current_settings(self):
        """Get current settings from UI controls"""
        # Map display text to internal value
        ref_baseline_map = {
            "Auto (Best Performance)": "auto",
            "Initial State": "initial",
            "Before Balancing": "before_balancing"
        }
        
        settings = {
            'BALANCE_THRESHOLD': self.balance_threshold_spin.value(),
            'MAX_PASSES': self.max_passes_spin.value(),
            'SWAP_AGGRESSIVENESS': self.swap_aggression_spin.value(),
            'MIN_STAT_THRESHOLD': self.min_stat_spin.value(),
            'OUTFIT_STRATEGY': self.outfit_strategy_combo.currentText(),
            'ENABLE_CROSS_STAT_BALANCING': self.cross_stat_check.isChecked(),
            'REFERENCE_BASELINE': ref_baseline_map.get(self.ref_baseline_combo.currentText(), 'auto'),
            'ROOM_PRIORITIES': {
                room_type: spin.value() 
                for room_type, spin in self.priority_spins.items()
            }
        }
        return settings
    
    def start_optimization(self):
        """Start the optimization process with adaptive or manual settings"""
    
        # Get vault selection
        vault_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Vault Save File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
    
        if not vault_file:
            self.log("No vault file selected", "#ee5a6f")
            return
    
        # Extract vault name from file path
        self.vault_name = os.path.splitext(os.path.basename(vault_file))[0]
        self.log(f"Selected vault: {self.vault_name}", "#1dd1a1")
    
        # Initialize optimizer with manual mode status
        self.optimizer = AdaptiveVaultOptimizer(self.vault_name, manual_mode=self.manual_mode)
        self.log(f"Initialized optimizer in {'Manual' if self.manual_mode else 'Adaptive'} mode", "#48dbfb")
    
        # If in manual mode, update optimizer with current settings
        if self.manual_mode:
            current_settings = self.get_current_settings()
            self.optimizer.update_from_manual_settings(current_settings)
            self.log("Applied manual settings to optimizer", "#ffcc00")
    
        # Get optimization parameters for placementCalc
        optimizer_params = self.optimizer.get_optimization_params()
    
        # Create balancing config with optimizer parameters
        self.balancing_config = BalancingConfig(optimizer_params)
    
        # Log current optimization parameters
        self.log("\n--- Optimization Parameters ---", "#48dbfb")
        self.log(f"Balance Threshold: {optimizer_params['BALANCE_THRESHOLD']}", "#ffffff")
        self.log(f"Max Passes: {optimizer_params['MAX_PASSES']}", "#ffffff")
        self.log(f"Swap Aggressiveness: {optimizer_params['SWAP_AGGRESSIVENESS']}", "#ffffff")
        self.log(f"Min Stat Threshold: {optimizer_params['MIN_STAT_THRESHOLD']}", "#ffffff")
        self.log(f"Outfit Strategy: {optimizer_params['OUTFIT_STRATEGY']}", "#ffffff")
        self.log(f"Cross-Stat Balancing: {optimizer_params['ENABLE_CROSS_STAT_BALANCING']}", "#ffffff")
        self.log(f"Reference Baseline: {optimizer_params['REFERENCE_BASELINE']}", "#ffffff")
    
        if optimizer_params.get('ROOM_PRIORITIES'):
            self.log("Room Priorities:", "#ffffff")
            for room_type, priority in optimizer_params['ROOM_PRIORITIES'].items():
                self.log(f"  {room_type}: {priority}", "#ffffff")
    
        self.log("--- Starting Optimization ---\n", "#48dbfb")
    
        try:
            # Disable start button during optimization
            self.start_btn.setEnabled(False)
            self.start_btn.setText("⏳ OPTIMIZING...")
        
            # Run the actual optimization (call your placementCalc script)
            self.run_placement_calc(vault_file, optimizer_params)
        
            # After optimization completes
            self.log("\n✓ Optimization complete!", "#1dd1a1")
        
            # If in adaptive mode, analyze performance and suggest adjustments
            if not self.manual_mode:
                self.log("\n--- Adaptive Analysis ---", "#48dbfb")
                suggestions = self.optimizer.suggest_adjustments()
            
                if suggestions and suggestions.get('adjustments'):
                    self.log("⚠️ Performance issues detected - adjustments suggested", "#ffcc00")
                
                    # Ask user if they want to apply adjustments
                    reply = QMessageBox.question(
                        self,
                        "Adaptive Adjustments Available",
                        "The adaptive optimizer has suggested parameter adjustments.\n\n"
                        "Would you like to apply these adjustments for the next optimization cycle?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                
                    if reply == QMessageBox.Yes:
                        self.optimizer.apply_adjustments(auto_apply=True)
                        self.log("✓ Adaptive adjustments applied", "#1dd1a1")
                    else:
                        self.log("Adaptive adjustments declined", "#888888")
                else:
                    self.log("✓ Performance on track - no adjustments needed", "#1dd1a1")
        
        except Exception as e:
            self.log(f"\n✗ Optimization failed: {str(e)}", "#ee5a6f")
            QMessageBox.critical(self, "Optimization Error", f"An error occurred:\n\n{str(e)}")
    
        finally:
            # Re-enable start button
            self.start_btn.setEnabled(True)
            self.start_btn.setText("▶️ START OPTIMIZATION")

    def run_placement_calc(self, vault_file, optimizer_params):
        """
        Execute the placementCalc optimization with given parameters
        """
        self.log("Loading vault data...", "#48dbfb")
    
        try:
            # Load vault data to extract outfit list
            import json
        
            self.log(f"Reading vault file: {vault_file}", "#888888")
        
            with open(vault_file, 'r') as f:
                vault_data = json.load(f)
        
            # Extract outfit list from dwellers
            outfitlist = []
            dwellers = vault_data.get('dwellers', {}).get('dwellers', [])
        
            self.log(f"Found {len(dwellers)} dwellers in vault", "#888888")
        
            for dweller in dwellers:
                outfit = dweller.get('equipedOutfit', {}).get('id')
                if outfit:
                    outfitlist.append(outfit)
        
            self.log(f"Found {len(outfitlist)} outfits to optimize", "#1dd1a1")
        
            # Import placementCalc
            from placementCalc import run
        
            # Get just the filename (placementCalc expects it in Downloads folder)
            json_filename = os.path.basename(vault_file)
        
            self.log(f"Starting optimization with strategy: {optimizer_params.get('OUTFIT_STRATEGY')}", "#48dbfb")
        
            # Run optimization
            results_file = run(
                json_path=json_filename,
                outfitlist=outfitlist,
                vault_name=self.vault_name,
                optimizer_params=optimizer_params,
                balancing_config=None
            )
        
            # Load results if file was created
            if results_file and os.path.exists(results_file):
                self.log(f"Loading results from {results_file}", "#888888")
                with open(results_file, 'r') as f:
                    results = json.load(f)
            
                # Display results
                self.display_optimization_results(results)
            
                # Save performance history for adaptive learning
                self.save_performance_history(results)
            else:
                self.log("⚠️ No results file generated", "#ffcc00")
    
        except FileNotFoundError as e:
            self.log(f"✗ File not found: {str(e)}", "#ee5a6f")
            self.log("Make sure the vault file is in the Downloads folder", "#ffcc00")
    
        except ImportError as e:
            self.log(f"⚠️ placementCalc module not found: {str(e)}", "#ffcc00")
            self.log("Make sure placementCalc.py is in the same directory", "#ffcc00")
    
        except Exception as e:
            self.log(f"✗ Optimization error: {str(e)}", "#ee5a6f")
            import traceback
            error_details = traceback.format_exc()
            self.log(error_details, "#888888")
            QMessageBox.critical(
                self, 
                "Optimization Error", 
                f"An error occurred during optimization:\n\n{str(e)}\n\nCheck the log for details."
            )

    def display_optimization_results(self, results):
        """Display the optimization results in the GUI"""
    
        self.log("\n" + "="*60, "#ffffff")
        self.log("OPTIMIZATION RESULTS", "#1dd1a1")
        self.log("="*60, "#ffffff")
    
        if 'initial_time' in results:
            self.log(f"Initial State: {results['initial_time']:.1f}s", "#ffffff")
    
        if 'before_balance_time' in results:
            self.log(f"Before Balancing: {results['before_balance_time']:.1f}s", "#ffffff")
    
        if 'after_balance_time' in results:
            self.log(f"After Balancing: {results['after_balance_time']:.1f}s", "#ffffff")
    
        if 'with_outfits_time' in results:
            self.log(f"With Outfits: {results['with_outfits_time']:.1f}s", "#1dd1a1")
    
        # Calculate improvements
        if 'initial_time' in results and 'with_outfits_time' in results:
            improvement = results['initial_time'] - results['with_outfits_time']
            improvement_pct = (improvement / results['initial_time']) * 100
            self.log(f"\nTotal Improvement: {improvement:.1f}s ({improvement_pct:.1f}%)", "#1dd1a1")
    
        # Room-by-room breakdown
        if 'room_times' in results:
            self.log("\n--- Room Production Times ---", "#48dbfb")
            for room_key, time_data in results['room_times'].items():
                self.log(f"{room_key}: {time_data['final']:.1f}s (was {time_data['initial']:.1f}s)", "#ffffff")
    
        # Outfit assignments
        if 'outfit_assignments' in results:
            self.log(f"\nOutfits Assigned: {len(results['outfit_assignments'])}", "#ffcc00")

    def save_performance_history(self, results):
        """Save performance metrics for adaptive learning"""
    
        history_file = f"{self.vault_name}_performance_history.json"
    
        # Load existing history
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
        else:
            history = {
                'timestamps': [],
                'initial': [],
                'before_balance': [],
                'after_balance': [],
                'with_outfits': []
            }
    
        # Append new data
        from datetime import datetime
        history['timestamps'].append(datetime.now().isoformat())
        history['initial'].append(results.get('initial_time', 0))
        history['before_balance'].append(results.get('before_balance_time', 0))
        history['after_balance'].append(results.get('after_balance_time', 0))
        history['with_outfits'].append(results.get('with_outfits_time', 0))
    
        # Save updated history
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
        self.log(f"\n✓ Performance data saved to {history_file}", "#888888")


    def on_mode_changed(self):
        """Handle mode toggle between adaptive and manual"""
        if self.auto_mode_radio.isChecked():
            self.manual_mode = False
            self.manual_mode_radio.setChecked(False)
            self.disable_settings_controls()
            self.log("Switched to Adaptive Mode - AI will adjust settings", "#48dbfb")
        
            # Update optimizer if it exists
            if hasattr(self, 'optimizer') and self.optimizer:
                self.optimizer.set_manual_mode(False)
            
        elif self.manual_mode_radio.isChecked():
            self.manual_mode = True
            self.auto_mode_radio.setChecked(False)
            self.enable_settings_controls()
            self.log("Switched to Manual Mode - Using custom settings", "#ffcc00")
        
            # Update optimizer if it exists
            if hasattr(self, 'optimizer') and self.optimizer:
                self.optimizer.set_manual_mode(True)
                current_settings = self.get_current_settings()
                self.optimizer.update_from_manual_settings(current_settings)

    def save_settings(self):
        """Save current settings to file and update optimizer"""
        if not self.vault_name:
            QMessageBox.warning(self, "No Vault", "Please start optimization first to select a vault.")
            return
    
        settings = self.get_current_settings()
        settings_file = f"{self.vault_name}_manual_settings.json"
    
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
    
        # Update optimizer with new settings
        if hasattr(self, 'optimizer') and self.optimizer and self.manual_mode:
            self.optimizer.update_from_manual_settings(settings)
            # Recreate balancing config with new parameters
            optimizer_params = self.optimizer.get_optimization_params()
            self.balancing_config = BalancingConfig(optimizer_params)
    
        self.settings_status.setText(f"✓ Settings saved and applied to {settings_file}")
        self.log(f"Settings saved and applied to optimizer", "#1dd1a1")
    
        QTimer.singleShot(3000, lambda: self.settings_status.setText(""))

    def apply_settings_to_optimizer(self):
        """Apply current UI settings to the optimizer (called during optimization runs)"""
        if self.manual_mode and hasattr(self, 'optimizer') and self.optimizer:
            current_settings = self.get_current_settings()
            self.optimizer.update_from_manual_settings(current_settings)
            optimizer_params = self.optimizer.get_optimization_params()
            self.balancing_config = BalancingConfig(optimizer_params)
            return optimizer_params
        elif hasattr(self, 'optimizer') and self.optimizer:
            return self.optimizer.get_optimization_params()
        return None
    
    def load_settings(self):
        """Load settings from file"""
        if not self.vault_name:
            QMessageBox.warning(self, "No Vault", "Please start optimization first to select a vault.")
            return
        
        settings_file = f"{self.vault_name}_manual_settings.json"
        
        if not os.path.exists(settings_file):
            QMessageBox.information(self, "No Saved Settings", f"No saved settings found for {self.vault_name}")
            return
        
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            
            # Apply settings to UI
            self.balance_threshold_spin.setValue(settings.get('BALANCE_THRESHOLD', 5.0))
            self.max_passes_spin.setValue(settings.get('MAX_PASSES', 10))
            self.swap_aggression_spin.setValue(settings.get('SWAP_AGGRESSIVENESS', 1.0))
            self.min_stat_spin.setValue(settings.get('MIN_STAT_THRESHOLD', 5))
            
            strategy = settings.get('OUTFIT_STRATEGY', 'deficit_first')
            index = self.outfit_strategy_combo.findText(strategy)
            if index >= 0:
                self.outfit_strategy_combo.setCurrentIndex(index)
            
            self.cross_stat_check.setChecked(settings.get('ENABLE_CROSS_STAT_BALANCING', True))
            
            # Load reference baseline
            ref_baseline_reverse_map = {
                "auto": "Auto (Best Performance)",
                "initial": "Initial State",
                "before_balancing": "Before Balancing"
            }
            ref_baseline_text = ref_baseline_reverse_map.get(
                settings.get('REFERENCE_BASELINE', 'auto'), 
                'Auto (Best Performance)'
            )
            ref_index = self.ref_baseline_combo.findText(ref_baseline_text)
            if ref_index >= 0:
                self.ref_baseline_combo.setCurrentIndex(ref_index)
            
            # Load priorities
            priorities = settings.get('ROOM_PRIORITIES', {})
            for room_type, value in priorities.items():
                if room_type in self.priority_spins:
                    self.priority_spins[room_type].setValue(value)
            
            # Enable manual mode when loading settings
            self.manual_mode_radio.setChecked(True)
            self.manual_mode = True
            self.enable_settings_controls()
            
            self.settings_status.setText(f"✓ Settings loaded from {settings_file}")
            self.log(f"Settings loaded from {settings_file} - Switched to Manual Mode", "#1dd1a1")
            
            QTimer.singleShot(3000, lambda: self.settings_status.setText(""))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load settings: {str(e)}")
    
    def reset_settings(self):
        """Reset all settings to defaults"""
        reply = QMessageBox.question(
            self, 
            "Reset Settings", 
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.balance_threshold_spin.setValue(5.0)
            self.max_passes_spin.setValue(10)
            self.swap_aggression_spin.setValue(1.0)
            self.min_stat_spin.setValue(5)
            self.outfit_strategy_combo.setCurrentIndex(0)
            self.cross_stat_check.setChecked(True)
            self.ref_baseline_combo.setCurrentIndex(0)  # Reset to "Initial State"
            
            default_priorities = {'Medbay': 1, 'Power': 2, 'Water': 3, 'Food': 4}
            for room_type, spin in self.priority_spins.items():
                spin.setValue(default_priorities.get(room_type, 5))
            
            self.auto_mode_radio.setChecked(True)
            self.manual_mode = False
            
            self.settings_status.setText("✓ Settings reset to defaults")
            self.log("Settings reset to defaults", "#1dd1a1")
            
            QTimer.singleShot(3000, lambda: self.settings_status.setText(""))
    
    def create_right_panel(self):
        """Create right panel with tabs"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        tabs = QTabWidget()
        
        # Performance tab with two charts
        perf_tab = QWidget()
        perf_layout = QVBoxLayout(perf_tab)
        
        # Top chart - Performance over time (timeline)
        perf_label = QLabel("VAULT PERFORMANCE TIMELINE")
        perf_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffcc00; padding: 5px;")
        perf_layout.addWidget(perf_label)
        
        self.timeline_chart = PerformanceChart()
        perf_layout.addWidget(self.timeline_chart)
        
        # Bottom chart - Current cycle production times
        cycle_label = QLabel("CURRENT CYCLE - ROOM PRODUCTION TIMES")
        cycle_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffcc00; padding: 5px; margin-top: 10px;")
        perf_layout.addWidget(cycle_label)
        
        self.production_chart = ProductionBarChart()
        perf_layout.addWidget(self.production_chart)
        
        tabs.addTab(perf_tab, "📊 Performance")
        
        # Suggestions tab
        suggestions_tab = QWidget()
        suggestions_layout = QVBoxLayout(suggestions_tab)
        
        suggestions_label = QLabel("RECOMMENDED DWELLER ASSIGNMENTS")
        suggestions_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffcc00; padding: 5px;")
        suggestions_layout.addWidget(suggestions_label)
        
        self.suggestions_list = QTextEdit()
        self.suggestions_list.setReadOnly(True)
        suggestions_layout.addWidget(self.suggestions_list)
        
        tabs.addTab(suggestions_tab, "👥 Dweller Moves")
        
        # Stats tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        
        self.stats_display = QTextEdit()
        self.stats_display.setReadOnly(True)
        stats_layout.addWidget(self.stats_display)
        
        tabs.addTab(stats_tab, "📈 Statistics")
        
        # ── Vault Map tab (NEW) ──────────────────────────────────────────────
        self.vault_map_tab = VaultMapTab()
        tabs.addTab(self.vault_map_tab, "🗺️ Vault Map")
        
        # Settings tab
        settings_tab = self.create_settings_tab()
        tabs.addTab(settings_tab, "⚙️ Settings")
        
        layout.addWidget(tabs)
        return panel
    
    def load_fallout_tips(self):
        """Load Fallout Shelter tips"""
        tips = [
            "💡 Assign dwellers to rooms matching their highest SPECIAL stat for maximum efficiency.",
            "💡 Merge three rooms of the same type for maximum capacity and efficiency.",
            "💡 Upgrade rooms to level 3 before merging for best production rates.",
            "💡 Keep your vault's happiness above 75% to maximize production speed.",
            "💡 Train dwellers in their weakest stats during downtime to improve overall performance.",
            "💡 Power rooms benefit from Strength - assign your strongest dwellers there.",
            "💡 Water treatment needs Perception - your sharpest dwellers work best.",
            "💡 Diners and Gardens need Agility - quick dwellers make the best cooks.",
            "💡 Balance your resource production - running out of power affects everything.",
            "💡 Pregnant dwellers and children don't contribute to production.",
            "💡 Outfits with SPECIAL bonuses can dramatically improve room performance.",
            "💡 Radio rooms need Charisma to attract new dwellers faster.",
            "💡 Med bays require Intelligence for faster Stimpak production.",
            "💡 Science labs need Intelligence for RadAway production.",
            "💡 Storage rooms don't need dwellers - save them for production.",
        ]
        
        for tip in tips:
            self.tips_list.addItem(tip)
    
    def log(self, message, color="#00ff00"):
        """Add message to log console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f'<span style="color:{color}">[{timestamp}] {message}</span>')
    
    def handle_missing_outfits(self, missing_outfit_ids):
        """Handle missing outfit data by prompting user"""
        self.log(f"⚠ Found {len(missing_outfit_ids)} missing outfit(s) in database", "#ff6b6b")
        
        success, failed, cancelled = self.outfit_manager.prompt_for_missing_outfits(
            missing_outfit_ids, parent=self
        )
        
        if cancelled:
            self.log("⚠ Outfit entry cancelled by user", "#ff6b6b")
            QMessageBox.warning(
                self,
                "Optimization Cancelled",
                "Outfit data entry was cancelled. Optimization cannot continue without complete outfit data.",
                QMessageBox.Ok
            )
            self.stop_optimization()
        elif failed > 0:
            self.log(f"⚠ Failed to add {failed} outfit(s)", "#ff6b6b")
        else:
            self.log(f"✓ Successfully added {success} outfit(s) to database", "#1dd1a1")
    
    def start_optimization(self):
        """Start optimization thread"""
        vault_num = self.vault_input.text().strip()
        
        if not vault_num:
            self.log("⚠ ERROR: Please enter a vault number", "#ff0000")
            return
        
        self.vault_name = f"vault{vault_num}"
        self.is_running = True
        
        # Inform vault map tab of the selected vault
        self.vault_map_tab.set_vault_name(self.vault_name)
        
        # Get optimizer params based on mode
        optimizer_params = None
        if self.manual_mode:
            optimizer_params = self.get_current_settings()
            self.log(f"✓ Starting optimization for {self.vault_name} (Manual Mode)", "#ffcc00")
        else:
            self.log(f"✓ Starting optimization for {self.vault_name} (Adaptive Mode)", "#ffcc00")
        
        self.status_label.setText("Status: RUNNING")
        self.status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #00ff00;")
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.vault_input.setEnabled(False)
        
        # Start optimization thread
        self.optimization_thread = OptimizationThread(self.vault_name, [], optimizer_params)
        # Connect signals BEFORE starting the thread
        self.optimization_thread.cycle_complete.connect(self.on_cycle_complete)
        self.optimization_thread.error_occurred.connect(self.on_error)
        self.optimization_thread.dweller_suggestions.connect(self.update_suggestions)
        self.optimization_thread.missing_outfits_found.connect(self.handle_missing_outfits)
        # Connect new vault design signal to VaultMapTab (runs on main thread)
        self.optimization_thread.vault_design_ready.connect(self.vault_map_tab.set_vault_design)
        # Also inform the tab which vault is selected (optional, for manual reload)
        self.vault_map_tab.set_vault_name(self.vault_name)
        self.optimization_thread.start()
        
        # Start chart updates
        self.chart_timer.start(5000)  # Update every 5 seconds
    
    def stop_optimization(self):
        """Stop optimization thread"""
        if self.optimization_thread:
            self.log("⏹ Stopping optimization...", "#ffcc00")
            self.optimization_thread.stop()
            self.optimization_thread.wait()
        
        # Stop countdown timer
        if hasattr(self, 'countdown_timer'):
            self.countdown_timer.stop()
            
        self.is_running = False
        self.status_label.setText("Status: STOPPED")
        self.status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #ff6b6b;")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.vault_input.setEnabled(True)
        
        self.chart_timer.stop()
        self.log("✓ Optimization stopped", "#ffcc00")
        
        # Generate final report
        self.generate_final_report()
    
    def on_cycle_complete(self, cycle_num, stats):
        """Handle cycle completion"""
        self.cycle_label.setText(f"Cycles Completed: {cycle_num}")
        self.log(f"✓ Cycle #{cycle_num} completed at {stats['timestamp']}")
        
        # Reset and start countdown progress bar
        self.progress_bar.setValue(0)
        self.start_countdown_timer()
    
    def start_countdown_timer(self):
        """Start a 60-second countdown timer that updates the progress bar"""
        self.countdown_seconds = 0
        
        # Create a timer that fires every second
        if not hasattr(self, 'countdown_timer'):
            self.countdown_timer = QTimer()
            self.countdown_timer.timeout.connect(self.update_countdown)
        
        self.countdown_timer.start(1000)  # Update every 1 second
    
    def update_countdown(self):
        """Update progress bar during countdown"""
        if not self.is_running:
            self.countdown_timer.stop()
            return
        
        self.countdown_seconds += 1
        
        # Calculate progress (0-60 seconds = 0-100%)
        progress = int((self.countdown_seconds / 60) * 100)
        self.progress_bar.setValue(min(progress, 100))
        
        # Update countdown label
        remaining = 60 - self.countdown_seconds
        self.countdown_label.setText(f"Next cycle in: {remaining}s")
        
        # Stop timer after 60 seconds
        if self.countdown_seconds >= 60:
            self.countdown_timer.stop()
            self.countdown_seconds = 0
            self.countdown_label.setText("Next cycle in: Processing...")
    
    def on_error(self, error_msg):
        """Handle errors"""
        self.log(f"❌ ERROR: {error_msg}", "#ff0000")
        self.stop_optimization()
    
    def update_suggestions(self, suggestions):
        """Update dweller movement suggestions"""
        self.suggestions_list.clear()
        
        if not suggestions:
            self.suggestions_list.setHtml('<span style="color:#ffcc00; font-size: 20px;">No changes recommended at this time.</span>')
            return
        
        # Read from the optimization results file
        try:
            file_path = f"{self.vault_name}_optimization_results.json"
            self.log(f"Reading suggestions from: {file_path}", "#48dbfb")
            
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
    
            print("DEBUG: data type:", type(data))
            print("DEBUG: data keys:", data.keys() if isinstance(data, dict) else "NOT A DICT")
    
            # Extract dweller and outfit assignments
            dweller_data = data["dweller_assignments"]
            print("DEBUG: dweller_data type:", type(dweller_data))
            print("DEBUG: dweller_data content:", dweller_data)
    

            # Check if it's the nested structure with "dweller" key
            if isinstance(dweller_data, dict) and "dweller" in dweller_data:
                dweller_assigns = [dweller_data["dweller"]]
            elif isinstance(dweller_data, dict):
                dweller_assigns = list(dweller_data.values())
            elif isinstance(dweller_data, list):
                dweller_assigns = dweller_data
            else:
                dweller_assigns = []
    
            print("DEBUG: dweller_assigns type:", type(dweller_assigns))
            print("DEBUG: dweller_assigns content:", dweller_assigns)
            
            
        except FileNotFoundError:
            self.log(f"ERROR: File not found: {file_path}", "#ff0000")
            self.suggestions_list.setHtml('<span style="color:#ff0000; font-size: 20px;">Error: Optimization results file not found.</span>')
            return
        except Exception as e:
            self.log(f"ERROR reading suggestions: {str(e)}", "#ff0000")
            self.suggestions_list.setHtml(f'<span style="color:#ff0000; font-size: 20px;">Error: {str(e)}</span>')
            return
        

        # Build HTML display with improved UI
        html = '<div style="font-family: Consolas; color: #00ff00; padding: 20px;">'

        # Header with summary
        dwellers_moved = [d for d in dweller_assigns if d.get("dweller_moved") is not None]
        dwellers_with_outfits = [d for d in dweller_assigns if 'outfit' in d and d['outfit']]

        html += '<div style="padding: 20px; border-radius: 10px; border: 3px solid #ffcc00; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">'
        html += '<h1 style="color: #ffcc00; margin: 0 0 15px 0; font-size: 32px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);">📋 DWELLER OPTIMIZATION REPORT</h1>'
        html += '<div style="display: flex; gap: 20px; justify-content: space-around;">'
        html += f'<div style="text-align: center; flex: 1; padding: 15px; border-radius: 8px; border: 2px solid #ff6b6b;">'
        html += f'<div style="font-size: 42px; color: #ff6b6b; font-weight: bold;">{len(dwellers_moved)}</div>'
        html += f'<div style="font-size: 16px; color: #cccccc; margin-top: 5px;">ROOM MOVES</div>'
        html += '</div>'
        html += f'<div style="text-align: center; flex: 1; padding: 15px; border-radius: 8px; border: 2px solid #1dd1a1;">'
        html += f'<div style="font-size: 42px; color: #1dd1a1; font-weight: bold;">{len(dwellers_with_outfits)}</div>'
        html += f'<div style="font-size: 16px; color: #cccccc; margin-top: 5px;">OUTFIT CHANGES</div>'
        html += '</div>'
        html += f'<div style="text-align: center; flex: 1; padding: 15px; border-radius: 8px; border: 2px solid #48dbfb;">'
        html += f'<div style="font-size: 42px; color: #48dbfb; font-weight: bold;">{len(dweller_assigns)}</div>'
        html += f'<div style="font-size: 16px; color: #cccccc; margin-top: 5px;">TOTAL ACTIONS</div>'
        html += '</div>'
        html += '</div>'
        html += '</div>'

        # Tabbed sections
        html += '<div style="margin-top: 20px;">'

        # SECTION 1: Room Assignments
        html += '<div style=" border: 2px solid #ff6b6b; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">'
        html += '<div style="color: #ff6b6b; margin: 0 0 20px 0; font-size: 28px; border-bottom: 3px solid #ff6b6b; padding-bottom: 10px; display: flex; align-items: center;">'
        html += '<span style="font-size: 36px; margin-right: 10px;">🏠</span> ROOM ASSIGNMENTS'
        html += '</div>'

        if dwellers_moved:
            # Group by room type for easier tracking
            moves_by_room = {}
            for mo in dwellers_moved:
                move_info = mo.get("dweller_moved")
                to_room = move_info["to"]
                if to_room not in moves_by_room:
                    moves_by_room[to_room] = []
                moves_by_room[to_room].append(mo)
    
            for room, dwellers in sorted(moves_by_room.items()):
                # Room header
                html += f'<div style=" padding: 10px 15px; margin-top: 30px; border-radius: 8px; border-left: 5px solid #feca57;">'
                html += f'<div style="color: #feca57; margin-top: 50; font-size: 24px;">🎯 {room}</div>'
                html += f'<hr style="border: none; height: 3px; background: linear-gradient(to right, transparent, #ffcc00, transparent); margin: 5px 0;">'
                html += '</div>'
        
                for mo in dwellers:
                    name = mo.get("name")
                    id = mo.get("id")
                    move_info = mo.get("dweller_moved")
                    primary = mo.get("primary_stat")
                    stat = mo.get("stat_value")
            
                    html += f'<div style=" padding: 15px; margin-bottom: 30px; margin-left: 20px; border-radius: 8px; border-left: 4px solid #00ff00; position: relative;">'
            
                    # Dweller name and ID
                    html += f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
                    html += f'<div style="font-size: 24px; color: #ffcc00; font-weight: bold; margin-top: 15;">👤 {name}</div>'
                    html += f'<div style=" padding: 5px 12px; border-radius: 15px; font-size: 16px; color: #888888;">ID: {id}</div>'
                    html += '</div>'
            
                    # Movement path with arrow
                    html += '<div style=" padding: 12px; border-radius: 6px; margin-bottom: 10px;">'
                    html += '<table style="width: 100%; border-collapse: collapse;">'
                    html += '<tr>'
                    html += f'<td style="padding: 8px;  border: 2px solid #ff6b6b; border-radius: 5px; width: 45%; color: #ffffff; font-size: 18px;"><strong style="color: #ff6b6b;">FROM:</strong><br>{move_info["from"]}</td>'
                    html += '<td style="text-align: center; width: 10%; font-size: 28px; color: #00ff00;">➜</td>'
                    html += f'<td style="padding: 8px; border: 2px solid #1dd1a1; border-radius: 5px; width: 45%; color: #ffffff; font-size: 18px;"><strong style="color: #1dd1a1;">TO:</strong><br>{move_info["to"]}</td>'
                    html += '</tr>'
                    html += '</table>'
                    html += '</div>'
            
                    # Primary stat info
                    if primary and stat:
                        stat_colors = {
                            'Strength': '#ff6b6b',
                            'Perception': '#feca57',
                            'Endurance': '#ee5a6f',
                            'Charisma': '#ff69b4',
                            'Intelligence': '#48dbfb',
                            'Agility': '#1dd1a1',
                            'Luck': '#ffd700'
                        }
                        stat_color = stat_colors.get(primary, '#48dbfb')
                        html += f'<div style="display: inline-block; background-color: {stat_color}22; padding: 8px 14px; border-radius: 15px; border: 2px solid {stat_color};">'
                        html += f'<span style="color: {stat_color}; font-weight: bold; font-size: 16px;">⭐ {primary}: {stat}</span>'
                        html += '</div>'
            
                    html += '</div>'
                    html += '</div><div style="margin-bottom: 30px;"></div>'

        else:
            html += '<p style="text-align: center; font-size: 20px; color: #888888; padding: 40px;">✓ No room reassignments needed</p>'

        html += '</div>'  # End Room Assignments section
        html += '</div><div style="margin-bottom: 15px;"></div>'


        # SECTION 2: Outfit Assignments
        html += '<div style="border: 2px solid #1dd1a1; border-radius: 10px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">'
        html += '<div style="color: #1dd1a1; margin: 0 40px 20px 0; font-size: 28px; border-bottom: 3px solid #1dd1a1; padding-bottom: 10px; display: flex; align-items: center;">'
        html += '<span style="font-size: 36px; margin-right: 10px;">👔</span> OUTFIT ASSIGNMENTS'
        html += '</div>'

        if dwellers_with_outfits:
            for dweller in dwellers_with_outfits:
                outfit = dweller['outfit']
                name = dweller.get("name", "Unknown")
                id = dweller.get("id", "?")
        
                # Determine primary stat bonus and color
                strength_bonus = outfit.get('strength_bonus', 0)
                perception_bonus = outfit.get('perception_bonus', 0)
                agility_bonus = outfit.get('agility_bonus', 0)
        
                # Choose color based on highest bonus
                if strength_bonus >= perception_bonus and strength_bonus >= agility_bonus and strength_bonus > 0:
                    border_color = '#ff6b6b'  # Red for Strength
                elif perception_bonus >= agility_bonus and perception_bonus > 0:
                    border_color = '#feca57'  # Yellow for Perception
                elif agility_bonus > 0:
                    border_color = '#1dd1a1'  # Green for Agility
                else:
                    border_color = '#888888'  # Gray for no bonuses
        
                # Build stats display
                stats = []
                if strength_bonus > 0:
                    stats.append(f'<span style="color: #ff6b6b;">S+{strength_bonus}</span>')
                if perception_bonus > 0:
                    stats.append(f'<span style="color: #feca57;">P+{perception_bonus}</span>')
                if agility_bonus > 0:
                    stats.append(f'<span style="color: #1dd1a1;">A+{agility_bonus}</span>')
                stats_text = ' | '.join(stats) if stats else 'No bonuses'

                html += f'<hr style="border: none; height: 3px; background-color:{border_color}; margin: 5px 0;">'
                html += f'<div style="font-size: 24px; color: #ffcc00; font-weight: bold; margin-bottom: 5px; margin-top: 20px;">{name}</div>'
                html += f'<div style="font-size: 14px; color: #888888; margin-bottom: 5px;">ID: {id}</div>'
                html += f'<div style="font-size: 18px; color: {border_color}; font-weight: bold, margin-bottom: 5px;">{stats_text}</div>'
        
                # Outfit name
                html += f'<div style="font-size: 18px; color: #ffffff; margin-bottom: 15px;"><strong>Outfit name:</strong> {outfit.get("outfit_name", "Unknown")}</div>'
        
                # Location
                assigned_room = dweller.get('assigned_room', {})
                current_room = f"{assigned_room.get('room_type', '?')}-{assigned_room.get('room_level', '?')}-{assigned_room.get('room_size', '?')}-{assigned_room.get('room_number', '?')}"
                html += f'<div style="font-size: 18px; color: #ffffff;"><strong>Location:</strong> {current_room}</div>'

                # Warning if needs to remove from someone
                if outfit.get('previous_owner'):
                    prev_owner = outfit['previous_owner']
                    html += f'<div style="background-color: #ff6b6b22; padding: 10px 12px; border-radius: 5px; border: 2px solid #ff6b6b; margin-top: 15px;">'
                    html += f'<span style="color: #ff6b6b; font-weight: bold; font-size: 16px;">⚠️ FIRST REMOVE FROM:</span> <span style="color: #ffffff; font-size: 16px;">{prev_owner.get("dweller_name", "Unknown")} (ID: {prev_owner.get("dweller_id", "?")})</span>'
                    html += '</div>'
                html += f'<hr style="border: none; height: 3px; background-color:{border_color}; margin: 5px 0;">'
                html += '</div>'
        else:
            html += '<p style="text-align: center; font-size: 20px; color: #888888; padding: 40px;">✓ No outfit changes needed</p>'

        html += '</div>'  # End Outfit Assignments section
        html += '</div>'  # End main container
        html += '</div>'
        
        self.suggestions_list.setHtml(html)
    
    def update_chart(self):
        """Update both performance charts"""
        if self.vault_name:
            self.timeline_chart.update_plot(self.vault_name)
            
            # Update production bar chart with latest results
            results_file = f"{self.vault_name}_optimization_results.json"
            if os.path.exists(results_file):
                self.production_chart.update_plot(results_file)
    
    def generate_final_report(self):
        """Generate final statistics report with graphs for each cycle"""
        if not self.vault_name:
            return
        
        from VaultPerformanceTracker import VaultPerformanceTracker
        tracker = VaultPerformanceTracker(self.vault_name)
        stats = tracker.get_summary_stats()
        
        if not stats:
            return
    
        # Clear the stats display and set up scroll area
        if hasattr(self.stats_display, 'clear'):
            self.stats_display.clear()
    
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: #2b2b2b; border: none; }")
    
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
    
        # Add summary report at the top
        summary_label = QLabel(f"""
            <div style='background-color: #1e1e1e; padding: 15px; border-radius: 5px; margin-bottom: 10px;'>
            <h2 style='color: #ffd700; margin-top: 0;'>📊 FINAL PERFORMANCE REPORT</h2>
            <h3 style='color: #00ff00; margin-top: 0;'>Time(s) Are Abit Off From Actaul Game</h3>
            <p style='color: #00ff00;'><b>Total Cycles:</b> {stats['total_cycles']}</p>
            <p style='color: #00bfff;'><b>Average Initial Time:</b> {stats['avg_initial']}s</p>
            <p style='color: #00bfff;'><b>Average Optimized Time:</b> {stats['avg_final']}s</p>
            <p style='color: #ff69b4;'><b>Best Performance:</b> {stats['best_performance']}s</p>
            <p style='color: #ff6347;'><b>Worst Performance:</b> {stats['worst_performance']}s</p>
            <p style='color: #7fff00; font-size: 16px;'><b>Total Improvement:</b> {round(stats['avg_initial'] - stats['avg_final'], 2)}s 
            ({round(((stats['avg_initial'] - stats['avg_final']) / stats['avg_initial']) * 100, 1)}%)</p>
            </div>
        """)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)
    
        # Add graphs for each cycle using the actual data structure
        history = tracker.history
        num_cycles = len(history['timestamps'])
    
        for cycle_num in range(num_cycles):
            cycle_label = QLabel(f"<h3 style='color: #ffd700;'>Cycle {cycle_num + 1}</h3>")
            layout.addWidget(cycle_label)
        
            # Get timestamp for this cycle
            timestamp = history['timestamps'][cycle_num]
            date_str = datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S');
        
            # Create figure for this cycle showing the progression
            fig = Figure(figsize=(10, 5), facecolor='#2b2b2b')
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)
        
            # Data for this specific cycle
            stages = ['Initial', 'Before\nBalancing', 'After\nBalancing', 'With\nOutfits']
            times = [
                history['initial'][cycle_num],
                history['before_balance'][cycle_num],
                history['after_balance'][cycle_num],
                history['with_outfits'][cycle_num]
            ]
            colors = ['#ff6b6b', '#feca57', '#48dbfb', '#1dd1a1']
        
            # Create bar chart
            bars = ax.bar(stages, times, color=colors, alpha=0.8, edgecolor='white', linewidth=1.5)
        
            # Add value labels on bars
            for bar, time in zip(bars, times):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{time:.1f}s',
                       ha='center', va='bottom', color='white', fontweight='bold', fontsize=10)
        
            ax.set_ylabel('Production Time (s)', color='white', fontsize=11, fontweight='bold')
            ax.set_title(f'Optimization Progress - Cycle {cycle_num + 1}\n{date_str}', 
                        color='#ffd700', fontsize=12, fontweight='bold')
            ax.tick_params(colors='white', labelsize=9)
            ax.set_facecolor('#1e1e1e')
            ax.spines['bottom'].set_color('white')
            ax.spines['top'].set_color('white')
            ax.spines['right'].set_color('white')
            ax.spines['left'].set_color('white')
            ax.grid(True, alpha=0.3, color='gray', axis='y')
        
            fig.tight_layout()
            layout.addWidget(canvas)
        
            # Add cycle stats
            initial = history['initial'][cycle_num]
            final = history['with_outfits'][cycle_num]
            improvement = initial - final
            improvement_pct = (improvement / initial * 100) if initial > 0 else 0
        
            cycle_stats = QLabel(f"""
                <div style='background-color: #1e1e1e; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                <p style='color: #00bfff;'><b>Initial Time:</b> {initial}s</p>
                <p style='color: #00ff00;'><b>Final Time:</b> {final}s</p>
                <p style='color: #7fff00;'><b>Improvement:</b> {round(improvement, 2)}s ({round(improvement_pct, 1)}%)</p>
                <p style='color: #aaa;'><b>Recorded:</b> {date_str}</p>
                </div>
            """)
            cycle_stats.setWordWrap(True)
            layout.addWidget(cycle_stats)
        
            # Add separator
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet("background-color: #555;")
            layout.addWidget(separator)
    
        layout.addStretch()
        scroll.setWidget(container)
    
        # Replace the stats display widget with scroll area
        parent_layout = self.stats_display.parent().layout()
        if parent_layout:
            parent_layout.replaceWidget(self.stats_display, scroll)
            self.stats_display.deleteLater()
            self.stats_display = scroll
        else:
            # If no parent layout, just set the scroll as the new stats display
            self.stats_display = scroll
    
        self.log(f"📊 Final report generated with {stats['total_cycles']} cycle graphs")

    def check_updates_action(self):
        repo = "HaroldDjeumen/fallShel_efficiency-program"  
        self.log("Checking for updates...", "#48dbfb")
        self.update_thread = UpdateCheckThread(APP_VERSION, repo, asset_match="win")
        self.update_thread.finished_signal.connect(self.on_update_check_finished)
        self.update_thread.start()

    def on_update_check_finished(self, result: dict):
        if result.get('error'):
            self.log(f"Update check failed: {result['error']}", "#ff0000")
            QMessageBox.warning(self, "Update Check Failed", f"Failed to check for updates:\n{result['error']}", QMessageBox.Ok)
            return
        if not result.get('update_available'):
            self.log("No update available. You are on the latest version.", "#1dd1a1")
            QMessageBox.information(self, "No Update", "No update available. You are on the latest version.", QMessageBox.Ok)
            return
        installer = result.get('downloaded_installer')
        latest = result.get('latest_version')
        self.log(f"Update available: {latest}. Installer downloaded to {installer}", "#ffcc00")
        resp = QMessageBox.question(self, "Update available", f"Version {latest} is available. Install now?", QMessageBox.Yes | QMessageBox.No)
        if resp == QMessageBox.Yes and installer:
            try:
                updater.run_installer(installer)
                self.log("Installer launched. Exiting application to allow install.", "#ffcc00")
                QApplication.quit()
            except Exception as e:
                self.log(f"Failed to launch installer: {e}", "#ff0000")
                QMessageBox.critical(self, "Install Failed", f"Failed to launch installer:\n{e}", QMessageBox.Ok)


def main():
    app = QApplication(sys.argv)
    
    font = QFont("Consolas", 10)
    app.setFont(font)
    
    window = FalloutShelterGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()