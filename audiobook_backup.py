import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, KeyCode, Controller as KeyboardController, Listener as KeyboardListener
import pyautogui
import threading
import time
import mss
import cv2
import numpy as np

class AudioBook:
    def __init__(self, root):
        self.root = root
        self.root.title("AudioBook - V.01")
        self.root.geometry("800x600")
        
        # Data structures
        self.hotkeys = []
        self.config_file = "audiobook_config.json"
        self.recording_mode = False
        self.recorded_clicks = []
        self.active = True
        self.currently_pressed = set()
        self.triggered_hotkeys = set()
        
        # Auto-target HSV configuration (default values)
        self.hsv_config = {
            'lower_h1': 0, 'upper_h1': 10,
            'lower_h2': 170, 'upper_h2': 180,
            'lower_s': 100, 'upper_s': 255,
            'lower_v': 100, 'upper_v': 255,
            'calibrated': False,
            'template': None  # Will be loaded from config if calibrated
        }
        self.outline_template = None  # Numpy array for template matching
        self.outline_shape_signature = None  # Hu Moments for shape matching
        
        # Controllers
        self.mouse_controller = MouseController()
        
        # Load saved configuration
        self.load_config()
        
        # Create UI
        self.create_ui()
        
        # Start hotkey listener
        self.start_hotkey_listener()
    
    def create_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="AudioBook Hotkey Manager", font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # Status indicator
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.grid(row=1, column=0, columnspan=3, pady=5)
        
        self.status_label = ttk.Label(self.status_frame, text="Status: Active", foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.toggle_btn = ttk.Button(self.status_frame, text="Disable Hotkeys", command=self.toggle_active)
        self.toggle_btn.pack(side=tk.LEFT, padx=5)
        
        # Hotkey list
        list_frame = ttk.LabelFrame(main_frame, text="Configured Hotkeys", padding="10")
        list_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Treeview for hotkeys
        columns = ('Hotkey', 'Clicks', 'Delay (ms)')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        self.tree.heading('Hotkey', text='Hotkey')
        self.tree.heading('Clicks', text='Click Sequence')
        self.tree.heading('Delay (ms)', text='Delay Between Clicks')
        
        self.tree.column('Hotkey', width=150)
        self.tree.column('Clicks', width=400)
        self.tree.column('Delay (ms)', width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Add New Hotkey", command=self.add_hotkey_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_hotkey).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_hotkey).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🎯 Calibrar ao Vivo", command=self.calibrate_live_screenshot, style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📁 Calibrar Arquivo", command=self.calibrate_auto_target).pack(side=tk.LEFT, padx=5)
        
        # Instructions
        instructions = """
Instructions:
1. Click "Add New Hotkey" to create a new automation
2. Press the desired hotkey combination when prompted
3. Click on screen positions in order: Right-click position, then Left-click position
4. Set delay between clicks (in milliseconds)
5. Press your configured hotkey to execute the click sequence

Tips:
- Common delay: 50-100ms for fast clicks, 200-500ms for safer automation
- Character center position should be your second click (left-click target)
"""
        
        inst_frame = ttk.LabelFrame(main_frame, text="How to Use", padding="10")
        inst_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        inst_label = ttk.Label(inst_frame, text=instructions, justify=tk.LEFT)
        inst_label.pack()
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        self.refresh_tree()
    
    def toggle_active(self):
        self.active = not self.active
        if self.active:
            self.status_label.config(text="Status: Active", foreground="green")
            self.toggle_btn.config(text="Disable Hotkeys")
        else:
            self.status_label.config(text="Status: Disabled", foreground="red")
            self.toggle_btn.config(text="Enable Hotkeys")
    
    def refresh_tree(self):
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add hotkeys
        for hk in self.hotkeys:
            hotkey_str = '+'.join([k.upper() for k in hk['hotkey']])
            hk_type = hk.get('type', 'normal')
            
            if hk_type == 'offensive':
                auto_target = hk.get('auto_target', False)
                
                if auto_target:
                    # Auto-target: only 1 position (rune), scans screen
                    clicks_str = f"[AUTO-TARGET] Rune: ({hk['clicks'][0]['x']}, {hk['clicks'][0]['y']}) → Scans entire screen"
                else:
                    # Manual: 2 positions (rune + destination)
                    if len(hk['clicks']) >= 2:
                        clicks_str = f"[MANUAL] Rune: ({hk['clicks'][0]['x']}, {hk['clicks'][0]['y']}) → Dest: ({hk['clicks'][1]['x']}, {hk['clicks'][1]['y']})"
                    else:
                        clicks_str = f"[MANUAL] Rune: ({hk['clicks'][0]['x']}, {hk['clicks'][0]['y']}) → Center"
                delay_str = "N/A"
            else:
                clicks_str = f"Right-click ({hk['clicks'][0]['x']}, {hk['clicks'][0]['y']}) -> Left-click ({hk['clicks'][1]['x']}, {hk['clicks'][1]['y']})"
                delay_str = str(hk['delay'])
            
            self.tree.insert('', tk.END, values=(hotkey_str, clicks_str, delay_str))
    
    def calibrate_auto_target(self):
        """Interactive tool to calibrate auto-target HSV color detection"""
        from tkinter import filedialog
        
        dialog = tk.Toplevel(self.root)
        dialog.title("🎯 Auto-Target Calibration")
        dialog.geometry("680x650")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Auto-Target Color Calibration", font=('Arial', 14, 'bold')).pack(pady=15)
        
        instructions = """
INSTRUÇÕES SUPER SIMPLES:

1. No Tibia, clique em um monstro para aparecer o QUADRADO VERMELHO

2. Aperte Win+Shift+S (Snipping Tool) e selecione a área ao redor
   (PODE incluir o monstro, fundo, etc. - não precisa ser perfeito!)
   
3. Salve o print como "outline.png" (Desktop ou Downloads)

4. Clique em "Carregar Imagem" abaixo e selecione o arquivo

5. O AudioBook vai DETECTAR AUTOMATICAMENTE o outline vermelho
   e IGNORAR todo o resto (monstro, decorações, tochas, paredes)!

⚠️ IMPORTANTE:
- O quadrado vermelho TEM QUE estar na imagem
- Pode ter outras coisas vermelhas - elas serão ignoradas
- Não precisa cortar perfeito - só precisa ter o outline visível

💡 DICA: Tire um print largo mostrando o monstro + outline!
        """
        
        ttk.Label(dialog, text=instructions, justify=tk.LEFT, wraplength=600).pack(pady=10, padx=20)
        
        status_var = tk.StringVar(value="Aguardando imagem...")
        ttk.Label(dialog, textvariable=status_var, font=('Arial', 10, 'bold'), foreground='blue').pack(pady=10)
        
        result_frame = ttk.LabelFrame(dialog, text="Resultado da Calibração", padding="10")
        result_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        result_text = tk.Text(result_frame, height=8, width=70, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)
        
        def load_and_calibrate():
            try:
                # Ask user to select image file
                file_path = filedialog.askopenfilename(
                    title="Selecione a imagem do outline vermelho",
                    filetypes=[
                        ("Image files", "*.png *.jpg *.jpeg *.bmp"),
                        ("All files", "*.*")
                    ]
                )
                
                if not file_path:
                    return
                
                status_var.set("Analisando imagem...")
                dialog.update()
                
                # Load image
                img = cv2.imread(file_path)
                if img is None:
                    messagebox.showerror("Erro", "Não foi possível carregar a imagem!")
                    return
                
                # Convert to HSV
                img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                
                # Find all red pixels (both ranges)
                lower_red1 = np.array([0, 50, 50])
                upper_red1 = np.array([10, 255, 255])
                lower_red2 = np.array([160, 50, 50])
                upper_red2 = np.array([180, 255, 255])
                
                mask1 = cv2.inRange(img_hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(img_hsv, lower_red2, upper_red2)
                red_mask = cv2.bitwise_or(mask1, mask2)
                
                # INTELLIGENT OUTLINE DETECTION: Find rectangular contours
                contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if len(contours) == 0:
                    messagebox.showerror("Erro", "Nenhum outline vermelho detectado!\nTente capturar uma área com o quadrado vermelho.")
                    return
                
                # Find the largest rectangular contour (most likely the target outline)
                best_contour = None
                best_area = 0
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = float(w) / h if h > 0 else 0
                    
                    # Filter for square-ish shapes (target outline)
                    # Target is ~32x32 pixels, aspect ratio close to 1
                    if 0.7 < aspect_ratio < 1.3 and area > best_area and w > 10 and h > 10:
                        best_contour = contour
                        best_area = area
                
                if best_contour is None:
                    messagebox.showerror("Erro", "Não foi possível identificar o outline do target!\nTente capturar apenas o quadrado vermelho.")
                    return
                
                # Create mask with ONLY the outline BORDER (draw edge only, NOT filled!)
                # This ensures we sample ONLY the red border pixels, not interior
                outline_mask = np.zeros_like(red_mask)
                cv2.drawContours(outline_mask, [best_contour], -1, 255, thickness=2)
                
                # AND with original red mask to ensure we only get red pixels from the border
                outline_mask = cv2.bitwise_and(outline_mask, red_mask)
                
                # Get ONLY pixels from the outline border
                outline_pixels = img_hsv[outline_mask > 0]
                
                if len(outline_pixels) == 0:
                    messagebox.showerror("Erro", "Erro ao extrair pixels do outline!")
                    return
                
                # Calculate median HSV values of OUTLINE pixels only
                median_h = int(np.median(outline_pixels[:, 0]))
                median_s = int(np.median(outline_pixels[:, 1]))
                median_v = int(np.median(outline_pixels[:, 2]))
                
                # Calculate tolerance based on standard deviation
                std_h = int(np.std(outline_pixels[:, 0]))
                std_s = int(np.std(outline_pixels[:, 1]))
                std_v = int(np.std(outline_pixels[:, 2]))
                
                # Set tolerance (2x std dev for 95% coverage)
                h_tolerance = max(5, min(15, std_h * 2))
                s_tolerance = max(30, min(80, std_s * 2))
                v_tolerance = max(30, min(80, std_v * 2))
                
                # Get bounding box for display
                x, y, w, h = cv2.boundingRect(best_contour)
                
                # EXTRACT TEMPLATE: Save binary pattern AND contour shape signature
                # Template matching: pixel comparison (strict)
                # Shape matching: geometric signature (flexible, zoom-invariant)
                template_size = 32  # Normalize to 32x32
                outline_roi = outline_mask[y:y+h, x:x+w]
                template = cv2.resize(outline_roi, (template_size, template_size), interpolation=cv2.INTER_AREA)
                
                # Normalize template to 0-1 range
                template_normalized = template.astype(np.float32) / 255.0
                
                # Calculate Hu Moments for shape matching (scale/rotation invariant)
                # This is the "geometric signature" of the outline
                moments = cv2.moments(best_contour)
                hu_moments = cv2.HuMoments(moments).flatten().tolist()
                
                # Update HSV config with TEMPLATE and SHAPE SIGNATURE
                self.hsv_config = {
                    'lower_h1': max(0, median_h - h_tolerance),
                    'upper_h1': min(180, median_h + h_tolerance),
                    'lower_h2': 170,  # Keep secondary range for red wrap-around
                    'upper_h2': 180,
                    'lower_s': max(0, median_s - s_tolerance),
                    'upper_s': 255,
                    'lower_v': max(0, median_v - v_tolerance),
                    'upper_v': 255,
                    'calibrated': True,
                    'template': template_normalized.tolist(),  # Pixel pattern
                    'shape_signature': hu_moments  # Geometric signature (AI-like)
                }
                
                # Save configuration
                self.save_config()
                
                # Display results
                result_text.delete('1.0', tk.END)
                result_text.insert(tk.END, f"✅ CALIBRAÇÃO CONCLUÍDA COM SUCESSO!\n\n")
                result_text.insert(tk.END, f"Imagem analisada: {os.path.basename(file_path)}\n")
                result_text.insert(tk.END, f"🎯 OUTLINE DETECTADO AUTOMATICAMENTE!\n")
                result_text.insert(tk.END, f"  Tamanho: {w}x{h} pixels\n")
                result_text.insert(tk.END, f"  Pixels do outline: {len(outline_pixels)}\n")
                result_text.insert(tk.END, f"  Template salvo: 32x32 normalizado\n\n")
                result_text.insert(tk.END, f"Cor HSV calibrada:\n")
                result_text.insert(tk.END, f"  Hue: {median_h} (±{h_tolerance})\n")
                result_text.insert(tk.END, f"  Saturation: {median_s} (±{s_tolerance})\n")
                result_text.insert(tk.END, f"  Value: {median_v} (±{v_tolerance})\n\n")
                result_text.insert(tk.END, f"✅ Sistema AI-like configurado:\n")
                result_text.insert(tk.END, f"   1. Filtro de cor HSV personalizado\n")
                result_text.insert(tk.END, f"   2. Shape Recognition (Hu Moments)\n")
                result_text.insert(tk.END, f"   3. Template matching (backup)\n")
                result_text.insert(tk.END, f"   4. Funciona com zoom/scaling!\n")
                result_text.insert(tk.END, f"   5. Rejeita decorações automaticamente!\n\n")
                result_text.insert(tk.END, f"Próximo passo:\n")
                result_text.insert(tk.END, f"1. Feche esta janela\n")
                result_text.insert(tk.END, f"2. Crie/use hotkey ofensiva com auto-target\n")
                result_text.insert(tk.END, f"3. Teste no jogo!")
                
                status_var.set("✅ Calibração completa!")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro durante calibração: {e}")
                import traceback
                traceback.print_exc()
                status_var.set("❌ Erro durante calibração")
        
        # Buttons at the bottom
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15, padx=20)
        
        ttk.Button(button_frame, text="📁 Carregar Imagem do Outline", 
                  command=load_and_calibrate, 
                  style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Fechar", 
                  command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def add_hotkey_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Hotkey")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Step 1: Press your desired hotkey combination", font=('Arial', 12)).pack(pady=10)
        
        hotkey_var = tk.StringVar(value="Waiting for hotkey...")
        hotkey_label = ttk.Label(dialog, textvariable=hotkey_var, font=('Arial', 10, 'bold'), foreground='blue')
        hotkey_label.pack(pady=5)
        
        pressed_keys = {'keys': set(), 'combo': None}
        
        def on_press(key):
            try:
                k = key.char.lower() if hasattr(key, 'char') else key.name.lower()
                pressed_keys['keys'].add(k)
                hotkey_var.set('+'.join(sorted([k.upper() for k in pressed_keys['keys']])))
            except:
                pass
        
        def on_release(key):
            if pressed_keys['keys']:
                pressed_keys['combo'] = sorted(list(pressed_keys['keys']))
                hotkey_var.set('+'.join([k.upper() for k in pressed_keys['combo']]) + " (Saved!)")
                return False  # Stop listener
        
        listener = KeyboardListener(on_press=on_press, on_release=on_release)
        listener.start()
        
        def continue_to_clicks():
            if not pressed_keys['combo']:
                messagebox.showwarning("No Hotkey", "Please press a hotkey combination first!")
                return
            
            listener.stop()
            dialog.destroy()
            self.record_clicks_dialog(pressed_keys['combo'])
        
        ttk.Button(dialog, text="Continue to Click Recording", command=continue_to_clicks).pack(pady=20)
        ttk.Button(dialog, text="Cancel", command=lambda: [listener.stop(), dialog.destroy()]).pack()
    
    def record_clicks_dialog(self, hotkey_combo):
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Hotkey Type")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Step 2: Choose Hotkey Type", font=('Arial', 14, 'bold')).pack(pady=15)
        
        type_frame = ttk.LabelFrame(dialog, text="Select Type", padding="15")
        type_frame.pack(pady=10, padx=20, fill=tk.BOTH)
        
        type_var = tk.StringVar(value="normal")
        
        ttk.Radiobutton(
            type_frame,
            text="Normal (Runes/Fluids): Right-click item → Left-click character",
            variable=type_var,
            value="normal"
        ).pack(anchor=tk.W, pady=5)
        
        ttk.Radiobutton(
            type_frame,
            text="Offensive (Runas Ofensivas): Right-click item → Move to center (manual click)",
            variable=type_var,
            value="offensive"
        ).pack(anchor=tk.W, pady=5)
        
        def continue_to_recording():
            dialog.destroy()
            if type_var.get() == "normal":
                self.record_normal_clicks(hotkey_combo)
            else:
                self.record_offensive_clicks(hotkey_combo)
        
        ttk.Button(dialog, text="Continue to Recording", command=continue_to_recording).pack(pady=20)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()
    
    def record_normal_clicks(self, hotkey_combo):
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Click Positions - Normal")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Step 3: Record Click Positions", font=('Arial', 12)).pack(pady=10)
        
        instruction_text = """
1. Click "Start Recording"
2. Move your mouse to the ITEM position (rune/mana fluid)
3. Click to record the first position (will be RIGHT-CLICK)
4. Move your mouse to your CHARACTER position (center)
5. Click to record the second position (will be LEFT-CLICK)
        """
        
        ttk.Label(dialog, text=instruction_text, justify=tk.LEFT).pack(pady=10)
        
        status_var = tk.StringVar(value="Ready to record...")
        status_label = ttk.Label(dialog, textvariable=status_var, font=('Arial', 10, 'bold'))
        status_label.pack(pady=5)
        
        clicks_recorded = []
        
        def on_click(x, y, button, pressed):
            if pressed and len(clicks_recorded) < 2:
                clicks_recorded.append({'x': x, 'y': y})
                if len(clicks_recorded) == 1:
                    status_var.set(f"Position 1 recorded: ({x}, {y})\nNow click on your character position...")
                elif len(clicks_recorded) == 2:
                    status_var.set(f"Position 2 recorded: ({x}, {y})\nBoth positions saved!")
                    return False  # Stop listener
        
        def start_recording():
            status_var.set("Recording... Click on ITEM position first")
            dialog.after(100, lambda: mouse.Listener(on_click=on_click).start())
        
        ttk.Button(dialog, text="Start Recording", command=start_recording).pack(pady=10)
        
        # Delay configuration
        delay_frame = ttk.Frame(dialog)
        delay_frame.pack(pady=10)
        
        ttk.Label(delay_frame, text="Delay between clicks (ms):").pack(side=tk.LEFT)
        delay_var = tk.IntVar(value=100)
        delay_spinbox = ttk.Spinbox(delay_frame, from_=10, to=2000, textvariable=delay_var, width=10)
        delay_spinbox.pack(side=tk.LEFT, padx=5)
        
        def save_hotkey():
            if len(clicks_recorded) != 2:
                messagebox.showwarning("Incomplete", "Please record both click positions!")
                return
            
            new_hotkey = {
                'hotkey': hotkey_combo,
                'clicks': clicks_recorded,
                'delay': delay_var.get(),
                'type': 'normal'
            }
            
            self.hotkeys.append(new_hotkey)
            self.save_config()
            self.refresh_tree()
            dialog.destroy()
            messagebox.showinfo("Success", f"Hotkey {'+'.join([k.upper() for k in hotkey_combo])} added successfully!")
        
        ttk.Button(dialog, text="Save Hotkey", command=save_hotkey).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()
    
    def record_offensive_clicks(self, hotkey_combo):
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Positions - Offensive Rune")
        dialog.geometry("550x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Step 3: Choose Auto-Target Mode", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Auto-target option at TOP
        auto_target_frame = ttk.LabelFrame(dialog, text="Target Detection Mode", padding="15")
        auto_target_frame.pack(pady=10, padx=20, fill=tk.X)
        
        auto_target_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            auto_target_frame,
            text="✓ Enable Auto-Target (RECOMMENDED)",
            variable=auto_target_var,
            command=lambda: update_instructions()
        ).pack(anchor=tk.W)
        
        ttk.Label(
            auto_target_frame,
            text="✓ Scans ENTIRE screen for red target outline (32x32px)\n✓ Automatically clicks on detected target\n✓ Works even when monster MOVES around!",
            font=('Arial', 9),
            foreground='green'
        ).pack(anchor=tk.W, pady=5)
        
        ttk.Label(
            auto_target_frame,
            text="✗ Manual Mode: Fixed destination position (manual click required)",
            font=('Arial', 9),
            foreground='gray'
        ).pack(anchor=tk.W)
        
        # Instructions change based on mode
        instruction_frame = ttk.LabelFrame(dialog, text="Recording Instructions", padding="10")
        instruction_frame.pack(pady=10, padx=20, fill=tk.X)
        
        instruction_var = tk.StringVar()
        ttk.Label(instruction_frame, textvariable=instruction_var, justify=tk.LEFT, wraplength=480).pack()
        
        def update_instructions():
            if auto_target_var.get():
                instruction_var.set(
                    "AUTO-TARGET MODE:\n"
                    "1. Click 'Start Recording'\n"
                    "2. Click ONLY the RUNE position (1 click)\n"
                    "3. Done!\n\n"
                    "When you press hotkey:\n"
                    "• Right-click on rune\n"
                    "• Scans screen for red outline\n"
                    "• Auto-clicks on target!"
                )
            else:
                instruction_var.set(
                    "MANUAL MODE:\n"
                    "1. Click 'Start Recording'\n"
                    "2. Click the RUNE position (1st click)\n"
                    "3. Click destination position (2nd click)\n\n"
                    "When you press hotkey:\n"
                    "• Right-click on rune\n"
                    "• Moves to destination\n"
                    "• You click manually"
                )
        
        update_instructions()
        
        status_var = tk.StringVar(value="Ready to record...")
        ttk.Label(dialog, textvariable=status_var, font=('Arial', 10, 'bold'), foreground='blue').pack(pady=10)
        
        clicks_recorded = []
        
        def on_click(x, y, button, pressed):
            if pressed and button == mouse.Button.left:
                clicks_recorded.append({'x': x, 'y': y})
                
                if auto_target_var.get():
                    # Auto-target: only 1 click needed
                    status_var.set(f"✓ Rune position recorded: ({x}, {y})\nReady to save!")
                    return False
                else:
                    # Manual: 2 clicks needed
                    if len(clicks_recorded) == 1:
                        status_var.set(f"✓ Rune recorded: ({x}, {y})\nNow click destination position...")
                    elif len(clicks_recorded) == 2:
                        status_var.set(f"✓ Complete! Rune: {clicks_recorded[0]}\nDestination: ({x}, {y})")
                        return False
        
        def start_recording():
            clicks_recorded.clear()
            if auto_target_var.get():
                status_var.set("Recording... Click RUNE position (1 click only)")
            else:
                status_var.set("Recording... Click RUNE position first")
            dialog.after(100, lambda: mouse.Listener(on_click=on_click).start())
        
        ttk.Button(dialog, text="Start Recording", command=start_recording, style='Accent.TButton').pack(pady=15)
        
        def save_hotkey():
            required_clicks = 1 if auto_target_var.get() else 2
            if len(clicks_recorded) != required_clicks:
                messagebox.showwarning("Incomplete", f"Please record {required_clicks} position(s)!")
                return
            
            new_hotkey = {
                'hotkey': hotkey_combo,
                'clicks': clicks_recorded,
                'delay': 0,
                'type': 'offensive',
                'auto_target': auto_target_var.get()
            }
            
            self.hotkeys.append(new_hotkey)
            self.save_config()
            self.refresh_tree()
            dialog.destroy()
            
            mode_desc = "AUTO-TARGET (scans screen)" if auto_target_var.get() else "MANUAL (fixed position)"
            messagebox.showinfo("Success", f"Offensive hotkey {'+'.join([k.upper() for k in hotkey_combo])} added!\n\nMode: {mode_desc}")
        
        ttk.Button(dialog, text="Save Hotkey", command=save_hotkey).pack(pady=5)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)
    
    def edit_hotkey(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a hotkey to edit")
            return
        
        index = self.tree.index(selection[0])
        existing_hotkey = self.hotkeys[index]
        hk_type = existing_hotkey.get('type', 'normal')
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Hotkey")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Edit Hotkey Configuration", font=('Arial', 12)).pack(pady=10)
        
        # Display current hotkey
        current_hotkey_str = '+'.join([k.upper() for k in existing_hotkey['hotkey']])
        type_str = "OFFENSIVE" if hk_type == 'offensive' else "NORMAL"
        ttk.Label(dialog, text=f"Current Hotkey: {current_hotkey_str} [{type_str}]", font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Click positions
        ttk.Label(dialog, text="Click Positions:", font=('Arial', 10)).pack(pady=5)
        if hk_type == 'offensive':
            clicks_str = f"Rune Position (Right-click): ({existing_hotkey['clicks'][0]['x']}, {existing_hotkey['clicks'][0]['y']})\n"
            if len(existing_hotkey['clicks']) >= 2:
                clicks_str += f"Destination Position: ({existing_hotkey['clicks'][1]['x']}, {existing_hotkey['clicks'][1]['y']})"
            else:
                clicks_str += "Destination: Center of screen (old format)"
        else:
            clicks_str = f"Position 1 (Right-click): ({existing_hotkey['clicks'][0]['x']}, {existing_hotkey['clicks'][0]['y']})\n"
            clicks_str += f"Position 2 (Left-click): ({existing_hotkey['clicks'][1]['x']}, {existing_hotkey['clicks'][1]['y']})"
        ttk.Label(dialog, text=clicks_str, justify=tk.LEFT).pack(pady=5)
        
        # Delay configuration (only for normal type)
        if hk_type == 'normal':
            delay_frame = ttk.Frame(dialog)
            delay_frame.pack(pady=10)
            
            ttk.Label(delay_frame, text="Delay between clicks (ms):").pack(side=tk.LEFT)
            delay_var = tk.IntVar(value=existing_hotkey['delay'])
            delay_spinbox = ttk.Spinbox(delay_frame, from_=10, to=2000, textvariable=delay_var, width=10)
            delay_spinbox.pack(side=tk.LEFT, padx=5)
        else:
            delay_var = tk.IntVar(value=0)
        
        # Options
        ttk.Label(dialog, text="\nWhat would you like to edit?", font=('Arial', 10)).pack(pady=10)
        
        def update_delay_only():
            if hk_type == 'normal':
                self.hotkeys[index]['delay'] = delay_var.get()
                self.save_config()
                self.refresh_tree()
                dialog.destroy()
                messagebox.showinfo("Success", "Delay updated successfully!")
        
        def re_record_clicks():
            dialog.destroy()
            if hk_type == 'offensive':
                self.record_offensive_clicks_edit(index, existing_hotkey['hotkey'])
            else:
                self.record_normal_clicks_edit(index, existing_hotkey['hotkey'], delay_var.get())
        
        def change_hotkey_combo():
            dialog.destroy()
            self.add_hotkey_dialog_edit(index, existing_hotkey['clicks'], delay_var.get(), hk_type)
        
        if hk_type == 'normal':
            ttk.Button(dialog, text="Update Delay Only", command=update_delay_only).pack(pady=5)
        ttk.Button(dialog, text="Re-record Click Positions", command=re_record_clicks).pack(pady=5)
        ttk.Button(dialog, text="Change Hotkey Combination", command=change_hotkey_combo).pack(pady=5)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=10)
    
    def record_normal_clicks_edit(self, index, hotkey_combo, delay):
        """Edit mode: re-record clicks for existing normal hotkey"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Re-record Click Positions - Normal")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Re-record Click Positions", font=('Arial', 12)).pack(pady=10)
        
        instruction_text = """
1. Click "Start Recording"
2. Move your mouse to the ITEM position (rune/mana fluid)
3. Click to record the first position (will be RIGHT-CLICK)
4. Move your mouse to your CHARACTER position (center)
5. Click to record the second position (will be LEFT-CLICK)
        """
        
        ttk.Label(dialog, text=instruction_text, justify=tk.LEFT).pack(pady=10)
        
        status_var = tk.StringVar(value="Ready to record...")
        status_label = ttk.Label(dialog, textvariable=status_var, font=('Arial', 10, 'bold'))
        status_label.pack(pady=5)
        
        clicks_recorded = []
        
        def on_click(x, y, button, pressed):
            if pressed and len(clicks_recorded) < 2:
                clicks_recorded.append({'x': x, 'y': y})
                if len(clicks_recorded) == 1:
                    status_var.set(f"Position 1 recorded: ({x}, {y})\nNow click on your character position...")
                elif len(clicks_recorded) == 2:
                    status_var.set(f"Position 2 recorded: ({x}, {y})\nBoth positions saved!")
                    return False
        
        def start_recording():
            status_var.set("Recording... Click on ITEM position first")
            dialog.after(100, lambda: mouse.Listener(on_click=on_click).start())
        
        ttk.Button(dialog, text="Start Recording", command=start_recording).pack(pady=10)
        
        def save_changes():
            if len(clicks_recorded) != 2:
                messagebox.showwarning("Incomplete", "Please record both click positions!")
                return
            
            self.hotkeys[index]['clicks'] = clicks_recorded
            self.hotkeys[index]['delay'] = delay
            self.save_config()
            self.refresh_tree()
            dialog.destroy()
            messagebox.showinfo("Success", "Click positions updated successfully!")
        
        ttk.Button(dialog, text="Save Changes", command=save_changes).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()
    
    def record_offensive_clicks_edit(self, index, hotkey_combo):
        """Edit mode: re-record positions for existing offensive hotkey"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Re-record Positions - Offensive")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Re-record Offensive Positions", font=('Arial', 12)).pack(pady=10)
        
        instruction_text = """
1. Click "Start Recording"
2. Move your mouse to the OFFENSIVE RUNE position
3. Click to record the rune position (will be RIGHT-CLICK)
4. Move your mouse to where you want the cursor to stop
5. Click to record the destination position
        """
        
        ttk.Label(dialog, text=instruction_text, justify=tk.LEFT).pack(pady=10)
        
        status_var = tk.StringVar(value="Ready to record...")
        status_label = ttk.Label(dialog, textvariable=status_var, font=('Arial', 10, 'bold'))
        status_label.pack(pady=5)
        
        clicks_recorded = []
        
        def on_click(x, y, button, pressed):
            if pressed and len(clicks_recorded) < 2:
                clicks_recorded.append({'x': x, 'y': y})
                if len(clicks_recorded) == 1:
                    status_var.set(f"Rune position recorded: ({x}, {y})\nNow click where you want the mouse to stop...")
                elif len(clicks_recorded) == 2:
                    status_var.set(f"Destination recorded: ({x}, {y})\nBoth positions saved!")
                    return False
        
        def start_recording():
            status_var.set("Recording... Click on OFFENSIVE RUNE position first")
            dialog.after(100, lambda: mouse.Listener(on_click=on_click).start())
        
        ttk.Button(dialog, text="Start Recording", command=start_recording).pack(pady=10)
        
        def save_changes():
            if len(clicks_recorded) != 2:
                messagebox.showwarning("Incomplete", "Please record both positions!")
                return
            
            self.hotkeys[index]['clicks'] = clicks_recorded
            self.save_config()
            self.refresh_tree()
            dialog.destroy()
            messagebox.showinfo("Success", "Positions updated successfully!")
        
        ttk.Button(dialog, text="Save Changes", command=save_changes).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()
    
    def add_hotkey_dialog_edit(self, index, clicks, delay, hk_type):
        """Edit mode: change hotkey combination for existing hotkey"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Hotkey Combination")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Press your new hotkey combination", font=('Arial', 12)).pack(pady=10)
        
        hotkey_var = tk.StringVar(value="Waiting for hotkey...")
        hotkey_label = ttk.Label(dialog, textvariable=hotkey_var, font=('Arial', 10, 'bold'), foreground='blue')
        hotkey_label.pack(pady=5)
        
        pressed_keys = {'keys': set(), 'combo': None}
        
        def on_press(key):
            try:
                k = key.char.lower() if hasattr(key, 'char') else key.name.lower()
                pressed_keys['keys'].add(k)
                hotkey_var.set('+'.join(sorted([k.upper() for k in pressed_keys['keys']])))
            except:
                pass
        
        def on_release(key):
            if pressed_keys['keys']:
                pressed_keys['combo'] = sorted(list(pressed_keys['keys']))
                hotkey_var.set('+'.join([k.upper() for k in pressed_keys['combo']]) + " (Saved!)")
                return False
        
        listener = KeyboardListener(on_press=on_press, on_release=on_release)
        listener.start()
        
        def save_changes():
            if not pressed_keys['combo']:
                messagebox.showwarning("No Hotkey", "Please press a hotkey combination first!")
                return
            
            listener.stop()
            self.hotkeys[index]['hotkey'] = pressed_keys['combo']
            self.hotkeys[index]['delay'] = delay
            self.hotkeys[index]['type'] = hk_type
            self.save_config()
            self.refresh_tree()
            dialog.destroy()
            messagebox.showinfo("Success", "Hotkey combination updated successfully!")
        
        ttk.Button(dialog, text="Save Changes", command=save_changes).pack(pady=20)
        ttk.Button(dialog, text="Cancel", command=lambda: [listener.stop(), dialog.destroy()]).pack()
    
    def delete_hotkey(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a hotkey to delete")
            return
        
        index = self.tree.index(selection[0])
        del self.hotkeys[index]
        self.save_config()
        self.refresh_tree()
    
    def clear_all(self):
        if messagebox.askyesno("Clear All", "Are you sure you want to delete all hotkeys?"):
            self.hotkeys = []
            self.save_config()
            self.refresh_tree()
    
    def start_hotkey_listener(self):
        def on_press(key):
            if not self.active:
                return
            
            try:
                k = key.char.lower() if hasattr(key, 'char') else key.name.lower()
                self.currently_pressed.add(k)
                
                # Find all matching hotkeys (where hotkey is subset of currently pressed)
                matching_hotkeys = []
                for idx, hk in enumerate(self.hotkeys):
                    hotkey_set = set(hk['hotkey'])
                    if hotkey_set.issubset(self.currently_pressed) and idx not in self.triggered_hotkeys:
                        matching_hotkeys.append((idx, hk, len(hk['hotkey'])))
                
                # If multiple matches, prefer the most specific (longest) combination
                if matching_hotkeys:
                    matching_hotkeys.sort(key=lambda x: x[2], reverse=True)
                    idx, hk, _ = matching_hotkeys[0]
                    
                    # Latch ALL matching hotkeys to prevent auto-repeat from triggering shorter subsets
                    for match_idx, _, _ in matching_hotkeys:
                        self.triggered_hotkeys.add(match_idx)
                    
                    threading.Thread(target=self.execute_clicks, args=(hk,), daemon=True).start()
            except:
                pass
        
        def on_release(key):
            try:
                k = key.char.lower() if hasattr(key, 'char') else key.name.lower()
                self.currently_pressed.discard(k)
                
                # Reset triggered state for hotkeys that are no longer fully pressed
                for idx, hk in enumerate(self.hotkeys):
                    hotkey_set = set(hk['hotkey'])
                    if not hotkey_set.issubset(self.currently_pressed):
                        self.triggered_hotkeys.discard(idx)
            except:
                pass
        
        listener = KeyboardListener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
    
    def detect_red_target(self):
        """
        Detect red outline using EDGE-FIRST approach
        Pipeline: Edge Detection → Geometric Filtering → Color Validation
        This is MORE ROBUST than color-first because it finds shapes, not pixels
        Returns (x, y) coordinates of target center, or None if not found
        """
        try:
            print(f"\n🔍 EDGE-FIRST DETECTION (New Algorithm)")
            with mss.mss() as sct:
                # Capture ENTIRE primary monitor
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                
                # Convert BGRA to BGR then to grayscale
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                
                # STEP 1: EDGE DETECTION (finds ALL borders, not just red)
                # Apply Gaussian blur first to reduce noise
                img_blur = cv2.GaussianBlur(img_gray, (5, 5), 0)
                
                # Canny edge detection
                edges = cv2.Canny(img_blur, 50, 150)
                
                # STEP 2: MORPHOLOGICAL CLOSING (reconnects broken outline)
                # This is KEY - the outline appears as disconnected edges
                kernel = np.ones((3, 3), np.uint8)
                edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
                edges_dilated = cv2.dilate(edges_closed, kernel, iterations=1)
                
                # Find contours from edges
                contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                print(f"   Found {len(contours)} edge contours")
                
                # DEBUG: Save edges image
                debug_file = "debug_edges.png"
                cv2.imwrite(debug_file, edges_dilated)
                print(f"   💾 Saved edges to: {debug_file}")
                
                # Also need HSV for color validation
                img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                
                if contours:
                    # STEP 3: GEOMETRIC FILTERING (find squares with ~4 vertices)
                    valid_targets = []
                    
                    for c in contours:
                        # Approximate contour to polygon
                        epsilon = 0.04 * cv2.arcLength(c, True)
                        approx = cv2.approxPolyDP(c, epsilon, True)
                        
                        # Get bounding box
                        x, y, w, h = cv2.boundingRect(c)
                        area = cv2.contourArea(c)
                        
                        # Filter 1: Size (accept wide range 20-60px for different resolutions)
                        if not (20 <= w <= 60 and 20 <= h <= 60):
                            continue
                        
                        # Filter 2: Must be roughly square
                        aspect_ratio = float(w) / h if h > 0 else 0
                        if not (0.75 <= aspect_ratio <= 1.25):
                            continue
                        
                        # Filter 3: Polygon should be roughly rectangular (~4-8 vertices)
                        # Outline can be noisy so accept 3-8
                        num_vertices = len(approx)
                        if not (3 <= num_vertices <= 8):
                            continue
                        
                        print(f"      Geometric candidate: pos({x},{y}), size {w}x{h}, vertices:{num_vertices}")
                        
                        # STEP 4: COLOR VALIDATION (is the border red AND interior not red?)
                        # Extract regions
                        roi_hsv = img_hsv[y:y+h, x:x+w]
                        
                        # Define red mask (both ranges)
                        lower_red1 = np.array([0, 70, 50])
                        upper_red1 = np.array([10, 255, 255])
                        lower_red2 = np.array([170, 70, 50])
                        upper_red2 = np.array([180, 255, 255])
                        
                        mask1 = cv2.inRange(roi_hsv, lower_red1, upper_red1)
                        mask2 = cv2.inRange(roi_hsv, lower_red2, upper_red2)
                        red_mask = cv2.bitwise_or(mask1, mask2)
                        
                        # Check BORDER (outer 4-5 pixels)
                        border_width = max(2, min(4, w // 10))
                        border_mask = np.zeros_like(red_mask)
                        border_mask[:border_width, :] = 255  # top
                        border_mask[-border_width:, :] = 255  # bottom
                        border_mask[:, :border_width] = 255  # left
                        border_mask[:, -border_width:] = 255  # right
                        
                        border_red = cv2.bitwise_and(red_mask, border_mask)
                        border_red_pixels = cv2.countNonZero(border_red)
                        border_pixels = cv2.countNonZero(border_mask)
                        border_red_ratio = border_red_pixels / border_pixels if border_pixels > 0 else 0
                        
                        # Check CENTER (inner region)
                        center_margin = max(border_width + 2, w // 4)
                        if w > center_margin * 2 and h > center_margin * 2:
                            center_mask = red_mask[center_margin:-center_margin, center_margin:-center_margin]
                            center_red_pixels = cv2.countNonZero(center_mask)
                            center_pixels = center_mask.size
                            center_red_ratio = center_red_pixels / center_pixels if center_pixels > 0 else 0
                        else:
                            center_red_ratio = 0.0
                        
                        print(f"         Border red: {border_red_ratio:.0%}, Center red: {center_red_ratio:.0%}")
                        
                        # VALIDATION: Border should be mostly red (>40%), center should be mostly NOT red (<30%)
                        if border_red_ratio > 0.40 and center_red_ratio < 0.30:
                            print(f"         ✅ RED HOLLOW SQUARE FOUND!")
                            
                            # Calculate score
                            score = border_red_ratio * 0.6 + (1.0 - center_red_ratio) * 0.4
                            
                            valid_targets.append({
                                'x': x, 'y': y, 'w': w, 'h': h,
                                'border_red': border_red_ratio,
                                'center_red': center_red_ratio,
                                'vertices': num_vertices,
                                'score': score
                            })
                        else:
                            print(f"         ❌ Rejected (not red hollow square)")
                    
                    # STEP 5: SELECT BEST TARGET
                    if valid_targets:
                        # Sort by score
                        valid_targets.sort(key=lambda t: t['score'], reverse=True)
                        
                        # Show all candidates
                        print(f"\n🎯 EDGE-FIRST: {len(valid_targets)} targets found:")
                        for i, t in enumerate(valid_targets[:3]):  # Show top 3
                            print(f"   {i+1}. Pos({t['x']},{t['y']}), Size:{t['w']}x{t['h']}, Border:{t['border_red']:.0%}, Center:{t['center_red']:.0%}, Score:{t['score']:.2f}")
                        
                        # Pick best
                        target = valid_targets[0]
                        
                        # Threshold: Score > 0.55 (border mostly red, center mostly not red)
                        if target['score'] >= 0.55:
                            # Calculate center
                            center_x = target['x'] + target['w'] // 2
                            center_y = target['y'] + target['h'] // 2
                            
                            # Convert to absolute screen coordinates
                            screen_x = monitor['left'] + center_x
                            screen_y = monitor['top'] + center_y
                            
                            print(f"✅ TARGET FOUND at ({screen_x}, {screen_y})")
                            print(f"   Size: {target['w']}x{target['h']}, Score: {target['score']:.2f}")
                            return (screen_x, screen_y)
                        else:
                            print(f"⚠️ Best score too low: {target['score']:.2f} < 0.55")
                    else:
                        print(f"❌ No red hollow squares found")
                else:
                    print(f"❌ No edge contours found")
                
                return None
                
        except Exception as e:
            print(f"❌ Error detecting target: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def execute_clicks(self, hotkey_config):
                                
                                # HOLLOW SQUARE CHECK:
                                # Target outline is HOLLOW (only border, not filled)
                                # Border pixels should be ~15-30% of total area
                                # (4 sides × ~32 pixels × ~2px thick = ~256 pixels out of ~1024 = 25%)
                                fill_ratio = white_pixels / total_pixels if total_pixels > 0 else 0
                                
                                # Look for hollow squares (border only) - more tolerant range
                                if 0.08 <= fill_ratio <= 0.50:
                                    print(f"      DEBUG: Candidate at ({x},{y}), size {w}x{h}, fill_ratio {fill_ratio:.2f}")
                                    # CRITICAL CHECK: Verify CENTER is EMPTY (no red pixels)
                                    # Target outline is HOLLOW - center should be empty
                                    # Check inner 18x18 region (leave 7px border on each side for 32x32)
                                    border_size = max(6, w // 5)  # ~6px border for 32px square
                                    if w > border_size * 2 and h > border_size * 2:
                                        inner_x1 = border_size
                                        inner_y1 = border_size
                                        inner_x2 = w - border_size
                                        inner_y2 = h - border_size
                                        
                                        center_roi = roi_mask[inner_y1:inner_y2, inner_x1:inner_x2]
                                        center_pixels = cv2.countNonZero(center_roi) if center_roi.size > 0 else 999
                                        center_area = (inner_x2 - inner_x1) * (inner_y2 - inner_y1)
                                        center_fill = center_pixels / center_area if center_area > 0 else 1.0
                                        
                                        # CENTER MUST BE MOSTLY EMPTY (<= 45% red pixels in center)
                                        # More tolerant to handle anti-aliasing and different resolutions
                                        if center_fill <= 0.45:
                                            print(f"         ✓ Hollow center OK: {center_fill:.2f}")
                                            # BORDER THICKNESS CHECK
                                            # Calculate average border thickness
                                            # Perimeter of square ≈ 4 * w, border pixels should be perimeter × thickness
                                            expected_border_pixels = 4 * w * 2  # 2px thick border
                                            thickness_ratio = white_pixels / expected_border_pixels if expected_border_pixels > 0 else 0
                                            
                                            # Border should be 1-4 pixels thick (ratio 0.4 to 2.2)
                                            # Blur and morphology can expand edges, so we're lenient
                                            if 0.4 <= thickness_ratio <= 2.2:
                                                # Calculate score based on how close to ideal target
                                                # Ideal: 32x32, center mostly empty (<35%), ~2px border
                                                size_score = 1.0 - min(abs(w - 32) / 32, 1.0)
                                                hollow_score = 1.0 - min(center_fill / 0.35, 1.0)  # Lower center_fill = higher score
                                                thickness_score = 1.0 - min(abs(thickness_ratio - 1.0) / 1.0, 1.0)
                                                
                                                # SHAPE MATCHING (AI-like): Compare geometric signature
                                                shape_score = 0.0
                                                if has_shape_signature:
                                                    # Calculate Hu Moments for this candidate
                                                    candidate_moments = cv2.moments(c)
                                                    candidate_hu = cv2.HuMoments(candidate_moments).flatten()
                                                    
                                                    # Compare shapes using matchShapes (lower = more similar)
                                                    # Returns value 0-1+, we convert to 0-1 score
                                                    shape_distance = cv2.matchShapes(
                                                        candidate_hu.reshape(-1, 1),
                                                        self.outline_shape_signature.reshape(-1, 1),
                                                        cv2.CONTOURS_MATCH_I1,
                                                        0
                                                    )
                                                    # Convert distance to similarity score (0=perfect, 1+=different)
                                                    # Typical good matches are < 0.1, bad matches > 0.5
                                                    shape_score = max(0.0, 1.0 - min(shape_distance * 2, 1.0))
                                                
                                                # TEMPLATE MATCHING: Compare pixel pattern (optional, for extra precision)
                                                template_score = 0.0
                                                if has_template:
                                                    candidate_roi = roi_mask.astype(np.float32) / 255.0
                                                    candidate_resized = cv2.resize(candidate_roi, (32, 32), interpolation=cv2.INTER_AREA)
                                                    template_product = candidate_resized * self.outline_template
                                                    template_score = np.sum(template_product) / max(np.sum(candidate_resized), 1e-6)
                                                    template_score = min(template_score, 1.0)
                                                
                                                # Calculate final score (AI-like recognition)
                                                if has_shape_signature:
                                                    # SHAPE is HEAVILY dominant (best defense against decorations!)
                                                    if has_template:
                                                        # Both shape and template (most accurate)
                                                        total_score = (shape_score * 0.75 + template_score * 0.15 + hollow_score * 0.10)
                                                    else:
                                                        # Shape only (still very good)
                                                        total_score = (shape_score * 0.80 + size_score * 0.10 + hollow_score * 0.10)
                                                elif has_template:
                                                    # Template only (pixel-perfect)
                                                    total_score = (template_score * 0.80 + size_score * 0.10 + hollow_score * 0.10)
                                                else:
                                                    # Fallback to geometric heuristics
                                                    total_score = (size_score * 0.5 + hollow_score * 0.4 + thickness_score * 0.1)
                                                
                                                valid_targets.append({
                                                    'x': x, 'y': y, 'w': w, 'h': h,
                                                    'fill_ratio': fill_ratio,
                                                    'center_fill': center_fill,
                                                    'thickness_ratio': thickness_ratio,
                                                    'shape_score': shape_score,
                                                    'template_score': template_score,
                                                    'score': total_score
                                                })
                    
                    if valid_targets:
                        # Sort by score and pick the best match
                        # CRITICAL: Only consider targets above minimum threshold
                        valid_targets.sort(key=lambda t: t['score'], reverse=True)
                        
                        # Debug: ALWAYS show all candidates with scores
                        print(f"\n🎯 {len(valid_targets)} valid candidates found:")
                        for i, t in enumerate(valid_targets[:5]):  # Show top 5
                            shape_s = t.get('shape_score', 0.0)
                            template_s = t.get('template_score', 0.0)
                            print(f"   {i+1}. Pos({t['x']}, {t['y']}), Size:{t['w']}x{t['h']}, Shape:{shape_s:.0%}, Template:{template_s:.0%}, Final:{t['score']:.2f}")
                        
                        target = valid_targets[0]
                        
                        # VERY STRICT threshold to reject decorations/flags/torches
                        # Shape matching must be VERY confident to avoid false positives
                        if has_shape_signature:
                            min_score = 0.75  # Shape signature requires 75%+ match
                        elif has_template:
                            min_score = 0.70  # Template requires 70%+ match
                        else:
                            min_score = 0.50  # Fallback geometric scoring
                        
                        if target['score'] >= min_score:
                            # Calculate center
                            center_x = target['x'] + target['w'] // 2
                            center_y = target['y'] + target['h'] // 2
                            
                            # Convert to absolute screen coordinates
                            screen_x = monitor['left'] + center_x
                            screen_y = monitor['top'] + center_y
                            
                            if has_shape_signature:
                                print(f"✅ Target detected at ({screen_x}, {screen_y})")
                                print(f"   Size: {target['w']}x{target['h']}, Shape match: {target['shape_score']:.2%}, Final: {target['score']:.2f}")
                            elif has_template:
                                print(f"✅ Target detected at ({screen_x}, {screen_y})")
                                print(f"   Size: {target['w']}x{target['h']}, Template: {target['template_score']:.2%}, Final: {target['score']:.2f}")
                            else:
                                print(f"✅ Target detected at ({screen_x}, {screen_y})")
                                print(f"   Size: {target['w']}x{target['h']}, Score: {target['score']:.2f}")
                            return (screen_x, screen_y)
                        else:
                            if has_shape_signature:
                                print(f"⚠️ Best candidate rejected (score: {target['score']:.2f} < {min_score:.2f}, shape: {target['shape_score']:.2%})")
                            elif has_template:
                                print(f"⚠️ Best candidate rejected (score: {target['score']:.2f} < {min_score:.2f}, template: {target['template_score']:.2%})")
                            else:
                                print(f"⚠️ Best candidate rejected (score: {target['score']:.2f} < {min_score:.2f})")
                    else:
                        print(f"❌ Found {len(contours)} red contours but NONE passed filters")
                        print(f"   (size, aspect ratio, or hollow center checks failed)")
                else:
                    print(f"❌ No red pixels detected on screen!")
                    print(f"   HSV range: H={self.hsv_config['lower_h1']}-{self.hsv_config['upper_h1']}, S={self.hsv_config['lower_s']}-{self.hsv_config['upper_s']}, V={self.hsv_config['lower_v']}-{self.hsv_config['upper_v']}")
                
                return None
                
        except Exception as e:
            print(f"❌ Error detecting target: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def execute_clicks(self, hotkey_config):
        """Execute the click sequence for a hotkey"""
        try:
            clicks = hotkey_config['clicks']
            hk_type = hotkey_config.get('type', 'normal')
            
            if hk_type == 'offensive':
                # Offensive rune: Right-click on rune
                x1, y1 = clicks[0]['x'], clicks[0]['y']
                print(f"🎯 Moving to rune at ({x1}, {y1})...")
                pyautogui.moveTo(x1, y1, duration=0.1)
                time.sleep(0.05)
                print(f"🎯 Right-clicking rune...")
                pyautogui.click(x1, y1, button='right')
                time.sleep(0.05)
                print(f"✅ Right-clicked rune at ({x1}, {y1})")
                
                # Check if auto-target is enabled
                auto_target = hotkey_config.get('auto_target', False)
                
                if auto_target:
                    # AUTO-TARGET MODE: Scan ENTIRE screen for red target outline
                    print("🎯 Auto-target: Scanning screen for red target outline...")
                    time.sleep(0.1)  # Wait for rune menu
                    
                    # Scan entire screen for 32x32 red target box
                    target_pos = self.detect_red_target()
                    
                    if target_pos:
                        # Target found! Move and SINGLE CLICK
                        tx, ty = target_pos
                        print(f"🎯 Moving to target at ({tx}, {ty})...")
                        pyautogui.moveTo(tx, ty, duration=0.1)
                        time.sleep(0.05)
                        print(f"🎯 Left-clicking target...")
                        # SINGLE CLICK - attack the target!
                        pyautogui.click(tx, ty, button='left')
                        print(f"✅ Auto-target: Clicked target at ({tx}, {ty})")
                    else:
                        # No target found
                        print("⚠️ Auto-target: No 32x32 red target detected on screen")
                else:
                    # MANUAL MODE: Move to fixed destination position (no click)
                    if len(clicks) >= 2:
                        x2, y2 = clicks[1]['x'], clicks[1]['y']
                    else:
                        screen_width, screen_height = pyautogui.size()
                        x2, y2 = screen_width // 2, screen_height // 2
                    
                    time.sleep(0.1)
                    pyautogui.moveTo(x2, y2, duration=0.15)
                    print(f"🎮 Manual mode: Cursor at ({x2}, {y2}) - click manually on target")
                
            else:
                # Normal: Right-click on item, then left-click on character
                delay = hotkey_config['delay'] / 1000.0
                
                # First click - RIGHT CLICK on item position
                x1, y1 = clicks[0]['x'], clicks[0]['y']
                pyautogui.moveTo(x1, y1, duration=0.05)
                time.sleep(0.02)
                pyautogui.rightClick(x1, y1)
                
                # Delay between clicks
                time.sleep(delay)
                
                # Second click - LEFT CLICK on character position
                x2, y2 = clicks[1]['x'], clicks[1]['y']
                pyautogui.moveTo(x2, y2, duration=0.05)
                time.sleep(0.02)
                pyautogui.leftClick(x2, y2)
            
        except Exception as e:
            print(f"Error executing clicks: {e}")
    
    def save_config(self):
        """Save hotkeys and HSV calibration to JSON file"""
        try:
            config = {
                'hotkeys': self.hotkeys,
                'hsv_config': self.hsv_config
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def load_config(self):
        """Load hotkeys and HSV calibration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                # Handle old format (just hotkeys array)
                if isinstance(config, list):
                    self.hotkeys = config
                # Handle new format (dict with hotkeys + hsv_config)
                elif isinstance(config, dict):
                    self.hotkeys = config.get('hotkeys', [])
                    loaded_hsv = config.get('hsv_config', None)
                    if loaded_hsv:
                        self.hsv_config = loaded_hsv
                        # Load template if exists
                        if 'template' in loaded_hsv and loaded_hsv['template'] is not None:
                            self.outline_template = np.array(loaded_hsv['template'], dtype=np.float32)
                        # Load shape signature if exists
                        if 'shape_signature' in loaded_hsv and loaded_hsv['shape_signature'] is not None:
                            self.outline_shape_signature = np.array(loaded_hsv['shape_signature'], dtype=np.float64)
        except Exception as e:
            print(f"Error loading config: {e}")
            self.hotkeys = []

def main():
    root = tk.Tk()
    app = AudioBook(root)
    root.mainloop()

if __name__ == "__main__":
    main()
