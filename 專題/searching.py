import tkinter as tk
from tkinter import messagebox
import xml.etree.ElementTree as ET

class ContactViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Contact Viewer")

        # 設置介面元素
        self.label = tk.Label(root, text="輸入人名:")
        self.label.pack()

        self.name_entry = tk.Entry(root)
        self.name_entry.pack()

        self.search_button = tk.Button(root, text="查找", command=self.search_contacts)
        self.search_button.pack()

        self.result_text = tk.Text(root, height=10, width=50)
        self.result_text.pack()

        self.person_data = {}
        self.load_xml_data()

    def load_xml_data(self):
        xml_file_path = "contacts.xml"  # 替換成你的 XML 文件路徑
        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        for person in root.findall("Person"):
            name = person.get("name")
            direct_contacts = [contact.text for contact in person.find("DirectContacts").findall("Contact")]
            indirect_contacts = {contact.text: contact.get("source") for contact in person.find("IndirectContacts").findall("Contact")}

            self.person_data[name] = {
                "DirectContacts": direct_contacts,
                "IndirectContacts": indirect_contacts
            }

    def search_contacts(self):
        name = self.name_entry.get().strip()
        self.result_text.delete(1.0, tk.END)  # 清空之前的結果

        if name in self.person_data:
            contacts = self.person_data[name]
            self.result_text.insert(tk.END, f"Name: {name}\n")
            self.result_text.insert(tk.END, "直接接觸者:\n")
            for contact in contacts["DirectContacts"]:
                self.result_text.insert(tk.END, f"- {contact}\n")

            self.result_text.insert(tk.END, "間接接觸者:\n")
            for contact, source in contacts["IndirectContacts"].items():
                self.result_text.insert(tk.END, f"- {contact} (透過 {source})\n")

        else:
            messagebox.showerror("錯誤", "該人物不存在於系統中。")

if __name__ == "__main__":
    root = tk.Tk()
    viewer = ContactViewer(root)
    root.mainloop()
