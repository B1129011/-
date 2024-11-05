import face_recognition
import os
import sqlite3
import hashlib
import datetime
from PIL import Image
import pandas as pd
import shutil

# 定義 Person 類別
class Person:
    def __init__(self, name, face_encoding):
        self.name = name
        self.face_encoding = face_encoding
        self.direct_contacts = set()
        self.indirect_contacts = set()

# 建立資料表
def create_tables(cursor):
    cursor.execute('DROP TABLE IF EXISTS person')
    cursor.execute('DROP TABLE IF EXISTS contacts')

    cursor.execute('''
        CREATE TABLE person (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            face_encoding BLOB NOT NULL,
            hash TEXT NOT NULL UNIQUE
        );
    ''')
    
    cursor.execute('''
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            contact_type TEXT NOT NULL,
            source TEXT,
            last_contact_time TEXT,
            contact_location TEXT,
            FOREIGN KEY (person_id) REFERENCES person(id),
            FOREIGN KEY (contact_id) REFERENCES person(id),
            UNIQUE(person_id, contact_id, contact_type)
        );
    ''')

# 計算人臉編碼的哈希值
def compute_hash(face_encoding):
    return hashlib.sha256(face_encoding.tobytes()).hexdigest()

# 備份資料庫
def backup_database(db_path):
    if os.path.exists(db_path):
        backup_path = f"{db_path.split('.')[0]}_backup_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.db"
        shutil.copy(db_path, backup_path)
        print(f"Database backed up to {backup_path}")
    else:
        print("No existing database to back up.")

# 處理單張圖片並記錄直接接觸
def process_photo(photo_path, person_dict, output_folder, cursor, tolerance=0.5):
    img = face_recognition.load_image_file(photo_path)
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    current_photo_people = []

    for face_location, face_encoding in zip(face_locations, face_encodings):
        matched_person = None

        # 比對現有的已知人臉
        for person_name, person in person_dict.items():
            distance = face_recognition.face_distance([person.face_encoding], face_encoding)[0]
            if distance <= tolerance:
                matched_person = person_name
                break

        if matched_person:
            current_photo_people.append(matched_person)
        else:
            # 若無匹配，則新增新人物
            new_person_name = f"Person_{len(person_dict) + 1}"
            person_dict[new_person_name] = Person(new_person_name, face_encoding)
            current_photo_people.append(new_person_name)

            # 儲存人臉圖片
            top, right, bottom, left = face_location
            face_image = img[top:bottom, left:right]
            pil_image = Image.fromarray(face_image)
            person_image_path = os.path.join(output_folder, f"{new_person_name}.jpg")
            pil_image.save(person_image_path)
            print(f"Saved face image for {new_person_name} at {person_image_path}")

            # 插入新人物到資料庫
            person_hash = compute_hash(face_encoding)
            cursor.execute('''
                INSERT INTO person (name, face_encoding, hash) VALUES (?, ?, ?)''',
                (new_person_name, face_encoding.tobytes(), person_hash))
            cursor.connection.commit()

    # 記錄直接接觸
    for i in range(len(current_photo_people)):
        for j in range(len(current_photo_people)):
            if i != j:
                cursor.execute('SELECT id FROM person WHERE name = ?', (current_photo_people[i],))
                person_id = cursor.fetchone()[0]

                cursor.execute('SELECT id FROM person WHERE name = ?', (current_photo_people[j],))
                contact_id = cursor.fetchone()[0]

                last_contact_time = datetime.datetime.now().isoformat()
                contact_location = ""

                cursor.execute('''
                    INSERT INTO contacts (person_id, contact_id, contact_type, last_contact_time, contact_location)
                    VALUES (?, ?, 'direct', ?, ?)
                    ON CONFLICT(person_id, contact_id, contact_type) DO UPDATE SET last_contact_time = excluded.last_contact_time;
                ''', (person_id, contact_id, last_contact_time, contact_location))
                cursor.connection.commit()
                print(f"Direct contact recorded between {current_photo_people[i]} and {current_photo_people[j]}")

                # 更新直接接觸到 person_dict
                person_dict[current_photo_people[i]].direct_contacts.add(current_photo_people[j])

    return current_photo_people

# 更新間接接觸
def update_indirect_contacts(person_dict, cursor):
    for person_name, person in person_dict.items():
        all_direct_contacts = person.direct_contacts.copy()
        for direct_contact in all_direct_contacts:
            if direct_contact in person_dict:
                for indirect_contact in person_dict[direct_contact].direct_contacts:
                    if indirect_contact != person_name and indirect_contact not in person.direct_contacts:
                        person.indirect_contacts.add(indirect_contact)

                        cursor.execute('SELECT id FROM person WHERE name = ?', (person_name,))
                        person_id = cursor.fetchone()[0]

                        cursor.execute('SELECT id FROM person WHERE name = ?', (indirect_contact,))
                        indirect_contact_id = cursor.fetchone()[0]

                        contact_time = datetime.datetime.now().isoformat()
                        contact_location = ""

                        cursor.execute(''' 
                            INSERT INTO contacts (person_id, contact_id, contact_type, source, last_contact_time, contact_location)
                            VALUES (?, ?, 'indirect', ?, ?, ?)
                            ON CONFLICT(person_id, contact_id, contact_type) DO UPDATE SET last_contact_time = excluded.last_contact_time;
                        ''', (person_id, indirect_contact_id, direct_contact, contact_time, contact_location))
                        cursor.connection.commit()
                        print(f"Indirect contact recorded between {person_name} and {indirect_contact} via {direct_contact}")

# 匯出資料庫內容到 Excel
def export_to_excel(db_path, excel_path):
    conn = sqlite3.connect(db_path)
    
    person_df = pd.read_sql_query("SELECT * FROM person", conn)
    contacts_df = pd.read_sql_query("SELECT * FROM contacts", conn)
    
    # 確認資料表有內容才匯出
    if not person_df.empty or not contacts_df.empty:
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='w') as writer:
            person_df.to_excel(writer, sheet_name='Persons', index=False)
            contacts_df.to_excel(writer, sheet_name='Contacts', index=False)
        print(f"Data has been successfully exported to {excel_path}")
    else:
        print("No data to export. Ensure contacts and person data are inserted.")

    conn.close()

# 主函數
def main():
    db_path = 'contacts.db'
    backup_database(db_path)

    photo_folder = r"C:\Users\User\桌面\專題\photos_folder"
    output_folder = r"C:\Users\User\桌面\專題\detected_people"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    create_tables(cursor)

    person_dict = {}

    # 處理所有照片
    photos = [os.path.join(photo_folder, f) for f in os.listdir(photo_folder) if f.endswith(('jpg', 'jpeg', 'png'))]
    for photo in photos:
        process_photo(photo, person_dict, output_folder, cursor, tolerance=0.5)
        conn.commit()

    # 更新間接接觸並提交變更
    update_indirect_contacts(person_dict, cursor)
    conn.commit()

    conn.close()

    # 匯出資料庫內容到 Excel
    excel_output_path = 'contacts_data.xlsx'
    print("Starting data export to Excel...")
    export_to_excel(db_path, excel_output_path)
    print("Data export completed.")

if __name__ == "__main__":
    main()
