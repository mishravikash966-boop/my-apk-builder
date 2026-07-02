import time
import os
import hashlib
import uuid
import subprocess
from datetime import datetime, timedelta
import pandas as pd
import threading
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

LICENSE_FILE = "license.lic"
SECRET_SALT = "GM_EXTRACTOR_SECRET_2026"

def get_machine_id():
    """Generates a unique hardware ID based on motherboard UUID."""
    try:
        if os.name == 'nt':
            output = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].strip()
            if output: return hashlib.sha256(output.encode()).hexdigest()[:12].upper()
    except:
        pass
    # Fallback to MAC address
    mac = uuid.getnode()
    return hashlib.sha256(str(mac).encode()).hexdigest()[:12].upper()

def verify_key(machine_id, key):
    """Verifies if the activation key matches the machine and extracts expiry date."""
    try:
        parts = key.split("-")
        if len(parts) != 3: return False, None
        
        enc_date, hash_part = parts[1], parts[2]
        
        # Validate hash structure
        expected_hash = hashlib.sha256(f"{machine_id}{enc_date}{SECRET_SALT}".encode()).hexdigest()[:8].upper()
        if expected_hash != hash_part: return False, None
        
        # Decode date (YYYYMMDD)
        expiry_date = datetime.strptime(enc_date, "%Y%m%d")
        if datetime.now() > expiry_date:
            return False, "Expired"
        return True, expiry_date
    except:
        return False, None

# --- LICENSE CHECK POPUP WINDOW ---
class LicenseWindow(ctk.CTk):
    def __init__(self, success_callback):
        super().__init__()
        self.success_callback = success_callback
        self.title("Activation Required")
        self.geometry("450x300")
        self.resizable(False, False)
        
        self.machine_id = get_machine_id()

        self.lbl = ctk.CTkLabel(self, text="GM Extractor Pro - Licensing System", font=("Arial", 16, "bold"))
        self.lbl.pack(pady=15)

        self.id_lbl = ctk.CTkLabel(self, text=f"Your Machine ID (Send this to seller):", font=("Arial", 12))
        self.id_lbl.pack()
        
        self.id_entry = ctk.CTkEntry(self, width=320, justify="center")
        self.id_entry.insert(0, self.machine_id)
        self.id_entry.configure(state="readonly")
        self.id_entry.pack(pady=5)

        self.key_lbl = ctk.CTkLabel(self, text="Enter Activation Key:", font=("Arial", 12, "bold"))
        self.key_lbl.pack(pady=(10,0))
        
        self.key_entry = ctk.CTkEntry(self, placeholder_text="XXXX-XXXX-XXXX-XXXX", width=320, justify="center")
        self.key_entry.pack(pady=5)

        self.act_btn = ctk.CTkButton(self, text="Activate Software", fg_color="#10B981", command=self.activate)
        self.act_btn.pack(pady=15)

    def activate(self):
        input_key = self.key_entry.get().strip().upper()
        is_valid, exp_date = verify_key(self.machine_id, input_key)
        
        if is_valid:
            with open(LICENSE_FILE, "w") as f:
                f.write(input_key)
            messagebox.showinfo("Success", f"Software successfully activated! Valid till: {exp_date.strftime('%d-%b-%Y')}")
            self.destroy()
            self.success_callback()
        elif exp_date == "Expired":
            messagebox.showerror("Error", "This activation key has expired!")
        else:
            messagebox.showerror("Error", "Invalid Activation Key. Please try again.")

# --- SEARCH POPUP ---
class SearchPopup(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Search Details")
        self.geometry("400x250")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set() 

        self.label = ctk.CTkLabel(self, text="Enter Search Details", font=("Arial", 14, "bold"))
        self.label.pack(pady=15)
        self.keyword_entry = ctk.CTkEntry(self, placeholder_text="Keyword (e.g., Schools, Hospitals)", width=300)
        self.keyword_entry.pack(pady=10)
        self.location_entry = ctk.CTkEntry(self, placeholder_text="Location (e.g., Noida, Delhi)", width=300)
        self.location_entry.pack(pady=10)
        self.search_btn = ctk.CTkButton(self, text="Search & Launch", fg_color="#1E3A8A", font=("Arial", 12, "bold"), width=150, command=self.submit)
        self.search_btn.pack(pady=15)

    def submit(self):
        keyword = self.keyword_entry.get().strip()
        location = self.location_entry.get().strip()
        if not keyword or not location:
            messagebox.showwarning("Input Missing", "Kripya Keyword aur Location dono enter karein!", parent=self)
            return
        self.destroy()
        self.callback(keyword, location)

# --- MAIN APPLICATION ---
class GMExtractorApp(ctk.CTk):
    def __init__(self, exp_date):
        super().__init__()
        self.title(f"GM Extractor Pro - Registered Version (Expiry: {exp_date.strftime('%d-%b-%Y')})")
        self.geometry("900x650")
        self.driver = None
        self.extracted_data = []
        self.is_grabbing = False
        self.current_keyword = ""
        self.current_location = ""

        # --- HEADER ---
        self.top_bar = ctk.CTkFrame(self, height=50, fg_color="#1E3A8A", corner_radius=0)
        self.top_bar.pack(fill="x", side="top")
        self.title_label = ctk.CTkLabel(self.top_bar, text="GM Extractor Pro", text_color="white", font=("Arial", 18, "bold"))
        self.title_label.pack(side="left", padx=20)
        self.version_label = ctk.CTkLabel(self.top_bar, text="V-2.5.0", text_color="white")
        self.version_label.pack(side="right", padx=20)

        # --- STEP 1 ---
        self.step1_frame = ctk.CTkFrame(self, fg_color="white", border_color="#E5E7EB", border_width=2)
        self.step1_frame.pack(fill="x", padx=20, pady=10)
        self.step1_num = ctk.CTkLabel(self.step1_frame, text="1", fg_color="#10B981", text_color="white", width=40, height=40, corner_radius=20, font=("Arial", 16, "bold"))
        self.step1_num.pack(side="left", padx=15, pady=15)
        self.step1_right = ctk.CTkFrame(self.step1_frame, fg_color="transparent")
        self.step1_right.pack(side="left", fill="both", expand=True, padx=10)
        self.step1_text = ctk.CTkLabel(self.step1_right, text="Click below button to open browser and enter keywords", font=("Arial", 13, "bold"))
        self.step1_text.pack(anchor="w", pady=(10,2))
        self.start_btn = ctk.CTkButton(self.step1_right, text="START", fg_color="#1E3A8A", font=("Arial", 12, "bold"), width=120, command=self.open_search_popup)
        self.start_btn.pack(anchor="w", pady=(0,10))
        self.status1_lbl = ctk.CTkLabel(self.step1_frame, text="Status: Not Initialised", text_color="orange", font=("Arial", 12, "bold"))
        self.status1_lbl.pack(side="right", padx=20)

        # --- STEP 2 ---
        self.step2_frame = ctk.CTkFrame(self, fg_color="white", border_color="#E5E7EB", border_width=2)
        self.step2_frame.pack(fill="x", padx=20, pady=10)
        self.step2_num = ctk.CTkLabel(self.step2_frame, text="2", fg_color="#10B981", text_color="white", width=40, height=40, corner_radius=20, font=("Arial", 16, "bold"))
        self.step2_num.pack(side="left", padx=15, pady=15)
        self.step2_right = ctk.CTkFrame(self.step2_frame, fg_color="transparent")
        self.step2_right.pack(side="left", fill="both", expand=True, padx=10)
        self.email_chk = ctk.CTkCheckBox(self.step2_right, text="Grab the email ID after completing the data fetching.", font=("Arial", 13))
        self.email_chk.pack(anchor="w", pady=(10,5))
        self.btn_sub_frame = ctk.CTkFrame(self.step2_right, fg_color="transparent")
        self.btn_sub_frame.pack(anchor="w", pady=(0,10))
        self.grab_btn = ctk.CTkButton(self.btn_sub_frame, text="START GRABBING", fg_color="#1E3A8A", font=("Arial", 12, "bold"), command=self.start_grabbing_thread)
        self.grab_btn.pack(side="left", padx=(0,10))
        self.stop_btn = ctk.CTkButton(self.btn_sub_frame, text="STOP", fg_color="#1E3A8A", font=("Arial", 12, "bold"), command=self.stop_grabbing)
        self.stop_btn.pack(side="left")
        
        self.status2_frame = ctk.CTkFrame(self.step2_frame, fg_color="transparent")
        self.status2_frame.pack(side="right", padx=20)
        self.status2_lbl = ctk.CTkLabel(self.status2_frame, text="Status: Not Started", text_color="orange", font=("Arial", 12, "bold"))
        self.status2_lbl.pack(anchor="e")
        self.count_lbl = ctk.CTkLabel(self.status2_frame, text="Count: 0", font=("Arial", 12, "bold"))
        self.count_lbl.pack(anchor="e")

        # --- DATA GRID ---
        self.table_frame = ctk.CTkFrame(self, fg_color="white", border_color="#E5E7EB", border_width=2)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        columns = ("#", "Business Name", "Mobile Number", "Review Count", "Rating", "Category", "Address")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings")
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"), background="#F3F4F6")
        style.configure("Treeview", rowheight=25, font=("Arial", 10))
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=125, anchor="w" if col in ["Business Name", "Address"] else "center")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(fill="x", padx=20, pady=15)
        self.export_btn = ctk.CTkButton(self.bottom_frame, text="EXPORT EXCEL", fg_color="#1E3A8A", font=("Arial", 12, "bold"), width=150, command=self.export_data)
        self.export_btn.pack(side="right", padx=10)

    def open_search_popup(self):
        SearchPopup(self, self.on_search_submitted)

    def on_search_submitted(self, keyword, location):
        self.current_keyword = keyword
        self.current_location = location
        def launch():
            self.status1_lbl.configure(text="Status: Initialising...", text_color="blue")
            options = webdriver.ChromeOptions()
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            self.driver.implicitly_wait(0.5)
            search_query = f"{keyword} in {location}"
            encoded_query = search_query.replace(" ", "+")
            self.driver.get(f"https://www.google.com/maps/search/{encoded_query}")
            self.status1_lbl.configure(text="Status: Initialised", text_color="green")
        threading.Thread(target=launch).start()

    def start_grabbing_thread(self):
        if not self.driver: return
        if self.is_grabbing: return
        self.is_grabbing = True
        self.status2_lbl.configure(text="Status: Running", text_color="green")
        threading.Thread(target=self.real_grab_logic).start()

    def real_grab_logic(self):
        try:
            self.extracted_data.clear()
            for row in self.tree.get_children(): self.tree.delete(row)
            index, scroll_attempts = 1, 0
            while self.is_grabbing and index <= 150:
                cards = self.driver.find_elements(By.XPATH, '//a[contains(@href, "/maps/place/")]')
                if not cards: time.sleep(1); continue
                new_element = False
                for card in cards:
                    if not self.is_grabbing or index > 150: break
                    try:
                        name = card.get_attribute("aria-label")
                        if not name or "Review" in name or "Rating" in name: continue
                        if any(d[1] == name for d in self.extracted_data): continue
                        
                        new_element = True
                        self.driver.execute_script("arguments[0].click();", card)
                        time.sleep(2.5)

                        phone, address, rating, reviews = "Not Available", "Not Available", "N/A", "0"
                        try: rating = card.find_element(By.CSS_SELECTOR, "span.MW4etd").text
                        except: pass
                        try: reviews = card.find_element(By.CSS_SELECTOR, "span.UY7F9b").text.replace("(","").replace(")","")
                        except: pass
                        try: phone = self.driver.find_element(By.XPATH, '//button[contains(@data-item-id, "phone:tel:")]').get_attribute("data-item-id").replace("phone:tel:", "").strip()
                        except: pass
                        try: address = self.driver.find_element(By.XPATH, '//button[contains(@data-item-id, "address")]').get_attribute("aria-label").replace("Address: ", "").strip()
                        except: pass

                        row_data = (str(index), name, phone, reviews, rating, self.current_keyword, address)
                        self.extracted_data.append(row_data)
                        self.tree.insert("", "end", values=row_data)
                        self.count_lbl.configure(text=f"Count: {index}")
                        index += 1

                        try:
                            back_btn = self.driver.find_element(By.XPATH, '//button[@aria-label="Back" or @data-item-id="back"]')
                            self.driver.execute_script("arguments[0].click();", back_btn)
                            time.sleep(1.5)
                        except: pass
                    except: continue

                try:
                    self.driver.execute_script("var p = document.querySelector('div[role=\"feed\"]') || document.querySelector('.m6F1pf'); if(p) p.scrollTop += 600;")
                    time.sleep(1.5)
                except: break
                if not new_element:
                    scroll_attempts += 1
                    if scroll_attempts > 10: break
                else: scroll_attempts = 0
            self.status2_lbl.configure(text="Status: Completed", text_color="blue")
            self.is_grabbing = False
        except: self.is_grabbing = False

    def stop_grabbing(self):
        self.is_grabbing = False
        self.status2_lbl.configure(text="Status: Stopped", text_color="red")

    def export_data(self):
        if not self.extracted_data: return
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if file_path:
            pd.DataFrame(self.extracted_data, columns=["#", "Business Name", "Mobile Number", "Review Count", "Rating", "Category", "Address"]).to_excel(file_path, index=False)

def start_main_app(exp_date):
    app = GMExtractorApp(exp_date)
    app.mainloop()

if __name__ == "__main__":
    machine_id = get_machine_id()
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            saved_key = f.read().strip()
        is_valid, exp_date = verify_key(machine_id, saved_key)
        if is_valid:
            start_main_app(exp_date)
        else:
            lic_win = LicenseWindow(lambda: start_main_app(exp_date))
            lic_win.mainloop()
    else:
        lic_win = LicenseWindow(lambda: verify_key(machine_id, open(LICENSE_FILE).read().strip())[1])
        # Force fresh window trigger
        def reload_after_activation():
            with open(LICENSE_FILE, "r") as f:
                _, date_val = verify_key(machine_id, f.read().strip())
            start_main_app(date_val)
        lic_win = LicenseWindow(reload_after_activation)
        lic_win.mainloop()
