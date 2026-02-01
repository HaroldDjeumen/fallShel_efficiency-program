import os
import sys
import shutil
import sqlite3
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QComboBox, QPushButton, QMessageBox,
                               QGroupBox, QFormLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

def resource_path(relative_path: str):
    """Return absolute path to resource, works for dev and for PyInstaller onefile."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


class OutfitEntryDialog(QDialog):
    """Dialog for entering missing outfit information"""
    
    def __init__(self, outfit_id, parent=None):
        super().__init__(parent)
        self.outfit_id = outfit_id
        self.outfit_data = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle(f"Missing Outfit Data - ID: {self.outfit_id}")
        self.setMinimumWidth(500)
        
        # Apply Fallout theme
        self.setStyleSheet("""        
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #00ff00;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #2a2a2a;
                border: 2px solid #00ff00;
                border-radius: 3px;
                padding: 5px;
                color: #00ff00;
                font-size: 11px;
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
        """)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("⚠️ OUTFIT DATA REQUIRED")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffcc00; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Info message
        info_label = QLabel(f"Outfit ID '{self.outfit_id}' was not found in the database.\nPlease enter the outfit details below:")
        info_label.setStyleSheet("color: #ff6b6b; font-size: 11px; padding: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Wiki link
        wiki_label = QLabel('<a href="https://fallout.fandom.com/wiki/Fallout_Shelter_outfits" style="color: #48dbfb;">📖 Click here for Fallout Shelter Outfit Reference</a>')
        wiki_label.setOpenExternalLinks(True)  # Make link clickable
        wiki_label.setStyleSheet("padding: 5px; font-size: 11px;")
        wiki_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(wiki_label)
        
        # Form group
        form_group = QGroupBox("Outfit Information")
        form_layout = QFormLayout()
        
        # Outfit ID (read-only)
        self.id_input = QLineEdit(self.outfit_id)
        self.id_input.setReadOnly(True)
        self.id_input.setStyleSheet(self.id_input.styleSheet() + "background-color: #444444;")
        form_layout.addRow("Outfit ID:", self.id_input)
        
        # Outfit Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Ninja Outfit, Lab Coat, etc.")
        form_layout.addRow("Name:*", self.name_input)
        
        # SPECIAL bonuses
        self.strength_input = QLineEdit("0")
        self.strength_input.setPlaceholderText("0-7")
        form_layout.addRow("Strength Bonus:", self.strength_input)
        
        self.perception_input = QLineEdit("0")
        self.perception_input.setPlaceholderText("0-7")
        form_layout.addRow("Perception Bonus:", self.perception_input)
        
        self.endurance_input = QLineEdit("0")
        self.endurance_input.setPlaceholderText("0-7")
        form_layout.addRow("Endurance Bonus:", self.endurance_input)
        
        self.charisma_input = QLineEdit("0")
        self.charisma_input.setPlaceholderText("0-7")
        form_layout.addRow("Charisma Bonus:", self.charisma_input)
        
        self.intelligence_input = QLineEdit("0")
        self.intelligence_input.setPlaceholderText("0-7")
        form_layout.addRow("Intelligence Bonus:", self.intelligence_input)
        
        self.agility_input = QLineEdit("0")
        self.agility_input.setPlaceholderText("0-7")
        form_layout.addRow("Agility Bonus:", self.agility_input)
        
        self.luck_input = QLineEdit("0")
        self.luck_input.setPlaceholderText("0-7")
        form_layout.addRow("Luck Bonus:", self.luck_input)
        
        # Sex/Gender restriction
        self.sex_combo = QComboBox()
        self.sex_combo.addItems(["Any", "Male", "Female"])
        form_layout.addRow("Gender:", self.sex_combo)

        self.rarity_combo = QComboBox()
        self.rarity_combo.addItems(["Common", "Rare", "Legendary"])
        form_layout.addRow("Rarity/Worn by:", self.rarity_combo)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Required field note
        required_note = QLabel("* Required field")
        required_note.setStyleSheet("color: #ff6b6b; font-size: 10px; font-style: italic;")
        layout.addWidget(required_note)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 SAVE OUTFIT")
        self.save_btn.clicked.connect(self.save_outfit)
        button_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("❌ CANCEL")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def save_outfit(self):
        """Validate and save outfit data"""
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", 
                              "Outfit name is required!",
                              QMessageBox.Ok)
            return
        
        try:
            strength = int(self.strength_input.text() or "0")
            perception = int(self.perception_input.text() or "0")
            endurance = int(self.endurance_input.text() or "0")
            charisma = int(self.charisma_input.text() or "0")
            intelligence = int(self.intelligence_input.text() or "0")
            agility = int(self.agility_input.text() or "0")
            luck = int(self.luck_input.text() or "0")
            
            # Validate ranges
            if not (0 <= strength <= 7 and 0 <= perception <= 7 and 0 <= endurance <= 7 and
                    0 <= charisma <= 7 and 0 <= intelligence <= 7 and 0 <= agility <= 7 and 0 <= luck <= 7):
                raise ValueError("SPECIAL bonuses must be between 0 and 7")
                
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", 
                              f"Invalid SPECIAL values: {str(e)}",
                              QMessageBox.Ok)
            return
        
        sex = self.sex_combo.currentText()
        rarity = self.rarity_combo.currentText()
        
        self.outfit_data = {
            'item_id': self.outfit_id,
            'name': name,
            'strength': strength,
            'perception': perception,
            'endurance': endurance,
            'charisma': charisma,
            'intelligence': intelligence,
            'agility': agility,
            'luck': luck,
            'sex': sex,
            'RARITY / WORNBY': rarity
        }
        
        self.accept()
    
    def get_outfit_data(self):
        """Return the entered outfit data"""
        return self.outfit_data


class OutfitDatabaseManager:
    """Manages outfit database operations including missing outfit detection"""
    
    def __init__(self, db_path: str = None):
        """
        If db_path is None the bundled `vault.db` will be copied to a per-user writable
        location (APPDATA) on first run and that writable copy is used. This allows the
        exe produced by PyInstaller (--onefile) to bundle the DB while letting the app
        write to a safe location at runtime.
        """
        if db_path:
            self.db_path = db_path
            return

        # Path to bundled DB inside the package or _MEIPASS (when frozen)
        bundled_db = resource_path("vault.db")

        # Choose a writable per-user location for the runtime DB copy
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        user_dir = os.path.join(appdata, "fallShel_efficiency_program")
        os.makedirs(user_dir, exist_ok=True)
        user_db = os.path.join(user_dir, "vault.db")

        # If bundled DB exists and user copy is missing, copy it
        if os.path.exists(bundled_db) and not os.path.exists(user_db):
            try:
                shutil.copy2(bundled_db, user_db)
            except Exception:
                # If copy fails, fall back to using bundled path (read-only)
                self.db_path = bundled_db
            else:
                self.db_path = user_db
        elif os.path.exists(user_db):
            self.db_path = user_db
        elif os.path.exists(bundled_db):
            # No writable copy possible, use bundled DB (read-only)
            self.db_path = bundled_db
        else:
            # No DB available — create a new empty DB in user_dir
            self.db_path = user_db
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Minimal schema to avoid runtime crashes; adapt as needed
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Outfit (
                    Name TEXT,
                    `Item ID` TEXT PRIMARY KEY,
                    S INTEGER, P INTEGER, E INTEGER, C INTEGER, I INTEGER, A INTEGER, L INTEGER,
                    Sex TEXT,
                    `RARITY / WORNBY` TEXT
                )
            """)
            conn.commit()
            conn.close()
        
    def get_outfit_data(self, outfit_id):
        """Retrieve outfit data from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT Name, `Item ID`, S, P, E, C, I, A, L, Sex, `RARITY / WORNBY` FROM Outfit WHERE `Item ID` = ?",
            (outfit_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            name, item_id, s_mod, p_mod, e_mod, c_mod, i_mod, a_mod, l_mod, sex, rarity = result
            return {
                'name': name,
                'item_id': item_id,
                's': s_mod if s_mod is not None else 0,
                'p': p_mod if p_mod is not None else 0,
                'e': e_mod if e_mod is not None else 0,
                'c': c_mod if c_mod is not None else 0,
                'i': i_mod if i_mod is not None else 0,
                'a': a_mod if a_mod is not None else 0,
                'l': l_mod if l_mod is not None else 0,
                'sex': sex,
                'RARITY / WORNBY': rarity
            }
        return None
    
    def add_outfit(self, outfit_data):
        """Add new outfit to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO Outfit (Name, `Item ID`, S, P, E, C, I, A, L, Sex, `RARITY / WORNBY`)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outfit_data['name'],    
                outfit_data['item_id'],
                outfit_data['strength'],
                outfit_data['perception'],
                outfit_data['endurance'],
                outfit_data['charisma'],
                outfit_data['intelligence'],
                outfit_data['agility'],
                outfit_data['luck'],
                outfit_data['sex'],
                outfit_data['RARITY / WORNBY']
            ))
            
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Outfit already exists
            return False
        except Exception as e:
            print(f"Error adding outfit: {e}")
            return False
        finally:
            conn.close()
    
    def check_missing_outfits(self, outfit_ids):
        """Check which outfit IDs are missing from database"""
        missing = []
        for outfit_id in outfit_ids:
            if not self.get_outfit_data(outfit_id):
                missing.append(outfit_id)
        return missing
    
    def prompt_for_missing_outfits(self, outfit_ids, parent=None):
        """
        Show dialog for each missing outfit and add to database
        Returns: (success_count, failed_count, cancelled)
        """
        missing = self.check_missing_outfits(outfit_ids)
        
        if not missing:
            return len(outfit_ids), 0, False
        
        success_count = 0
        failed_count = 0
        
        for outfit_id in missing:
            dialog = OutfitEntryDialog(outfit_id, parent)
            result = dialog.exec()
            
            if result == QDialog.Accepted:
                outfit_data = dialog.get_outfit_data()
                if outfit_data and self.add_outfit(outfit_data):
                    success_count += 1
                else:
                    failed_count += 1
            else:
                # User cancelled
                return success_count, failed_count, True
        
        return success_count, failed_count, False