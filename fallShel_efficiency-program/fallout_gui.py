import sys
import os
import json
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QTextEdit, 
                               QLineEdit, QGroupBox, QListWidget, QTabWidget,
                               QProgressBar, QScrollArea, QFrame, QSplitter, QMessageBox)
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor, QPixmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from placementCalc import NULL
from outfit_manager import OutfitDatabaseManager
from version import __version__ as APP_VERSION
import updater

# Thread for running optimization cycles
class OptimizationThread(QThread):
    cycle_complete = Signal(int, dict)  # cycle_number, stats
    error_occurred = Signal(str)
    # accept any Python object (str path, dict, or list) from the worker
    dweller_suggestions = Signal(dict)
    missing_outfits_found = Signal(list)  # Signal for missing outfits
    
    def __init__(self, vault_name, outfit_list):
        super().__init__()
        self.vault_name = vault_name
        self.outfit_list = outfit_list
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
                
                # Get optimizer params
                optimizer_params = optimizer.get_optimization_params()
                
                # Run cycle
                json_path = sav_fetcher.run(self.vault_name)
                outfitlist = TableSorter.run(json_path)
                
                # Check for missing outfits
                outfit_manager = OutfitDatabaseManager()
                missing = outfit_manager.check_missing_outfits(outfitlist)
                
                if missing and self.cycle_count == 1:  # Only check on first cycle
                    self.missing_outfits_found.emit(missing)
                    # Pause thread until user handles missing outfits
                    while missing:
                        time.sleep(0.5)
                        # Recheck to see if they've been added
                        missing = outfit_manager.check_missing_outfits(outfitlist)
                        if not self.running:
                            return
                
                virtualvaultmap.run(json_path)
                
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
                
                # Every 5 cycles, run adaptive analysis
                if self.cycle_count % 2 == 0 and self.cycle_count >= 2:
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
            QLineEdit {
                background-color: #2a2a2a;
                border: 2px solid #00ff00;
                border-radius: 3px;
                padding: 5px;
                color: #00ff00;
                font-size: 11px;
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
        
        self.log(f"✓ Starting optimization for {self.vault_name}", "#ffcc00")
        self.status_label.setText("Status: RUNNING")
        self.status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #00ff00;")
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.vault_input.setEnabled(False)
        
        # Start optimization thread
        self.optimization_thread = OptimizationThread(self.vault_name, [])
        self.optimization_thread.cycle_complete.connect(self.on_cycle_complete)
        self.optimization_thread.error_occurred.connect(self.on_error)
        self.optimization_thread.dweller_suggestions.connect(self.update_suggestions)
        self.optimization_thread.missing_outfits_found.connect(self.handle_missing_outfits)
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

                # Create card with colored border - FIXED VERSION
                html += f'<hr style="border: none; height: 3px; background-color:{border_color}; margin: 5px 0;">'
        
                # Dweller name and ID
                html += f'<div style="font-size: 24px; color: #ffcc00; font-weight: bold; margin-bottom: 5px; margin-top: 20px;">{name}</div>'
                html += f'<div style="font-size: 14px; color: #888888; margin-bottom: 5px;">ID: {id}</div>'
        
                # Stat bonus
                html += f'<div style="font-size: 18px; color: {border_color}; font-weight: bold; margin-bottom: 5px;">{stats_text}</div>'
        
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
        repo = "HaroldDjeumen/fallShel_efficiency-program"  # change if repo differs
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
    
    # Set application font
    font = QFont("Consolas", 10)
    app.setFont(font)
    
    window = FalloutShelterGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()