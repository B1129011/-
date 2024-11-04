import face_recognition
import os
import sqlite3
import xml.etree.ElementTree as ET
from PIL import Image
import datetime

class Person:
    def __init__(self, name, face_encoding):
        self.name = name
        self.face_encoding = face_encoding
        self.direct_contacts = set()
        self.indirect_contacts = set()

def create_tables(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS person (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            face_encoding BLOB NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            contact_type TEXT NOT NULL,  -- 'direct' 或 'indirect'
            source TEXT,                  -- 來源（如果是間接接觸，則記錄來源人物）
            contact_time TEXT,            -- 接觸時間
            contact_location TEXT,         -- 接觸地點
            FOREIGN KEY (person_id) REFERENCES person(id),
            FOREIGN KEY (contact_id) REFERENCES person(id),
            UNIQUE(person_id, contact_id, contact_type)
        );
    ''')

def process_photo(photo_path, person_dict, output_folder, cursor):
    img = face_recognition.load_image_file(photo_path)
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    current_photo_people = []

    for face_location, face_encoding in zip(face_locations, face_encodings):
        matched_person = None
        for person_name, person in person_dict.items():
            match_results = face_recognition.compare_faces([person.face_encoding], face_encoding)
            if match_results[0]:
                matched_person = person_name
                break

        if matched_person:
            current_photo_people.append(matched_person)
        else:
            new_person_name = f"Person_{len(person_dict) + 1}"
            person_dict[new_person_name] = Person(new_person_name, face_encoding)
            current_photo_people.append(new_person_name)

            top, right, bottom, left = face_location
            face_image = img[top:bottom, left:right]
            pil_image = Image.fromarray(face_image)
            person_image_path = os.path.join(output_folder, f"{new_person_name}.jpg")
            pil_image.save(person_image_path)
            print(f"Saved face image for {new_person_name} at {person_image_path}")

            # 在資料庫中插入新人物
            cursor.execute('''
                INSERT INTO person (name, face_encoding) VALUES (?, ?)''',
                (new_person_name, face_encoding.tobytes()))

    # 記錄直接接觸
    for i in range(len(current_photo_people)):
        for j in range(len(current_photo_people)):
            if i != j:
                # 獲取人物ID
                cursor.execute('SELECT id FROM person WHERE name = ?', (current_photo_people[i],))
                person_id = cursor.fetchone()[0]

                cursor.execute('SELECT id FROM person WHERE name = ?', (current_photo_people[j],))
                contact_id = cursor.fetchone()[0]

                # 使用當前時間作為接觸時間
                contact_time = datetime.datetime.now().isoformat()

                # 使用空字符串或預設值作為接觸地點
                contact_location = ""  # 您可以根據需要指定一個地點

                # 插入直接接觸
                cursor.execute(''' 
                    INSERT OR IGNORE INTO contacts (person_id, contact_id, contact_type, contact_time, contact_location)
                    VALUES (?, ?, 'direct', ?, ?)''',
                    (person_id, contact_id, contact_time, contact_location))
                person_dict[current_photo_people[i]].direct_contacts.add(current_photo_people[j])

    return current_photo_people

def update_indirect_contacts(person_dict, cursor):
    for person_name, person in person_dict.items():
        all_direct_contacts = person.direct_contacts.copy()
        for contact in all_direct_contacts:
            for indirect_contact in person_dict[contact].direct_contacts:
                if indirect_contact != person_name and indirect_contact not in person.direct_contacts:
                    person.indirect_contacts.add(indirect_contact)

                    # 獲取人物ID
                    cursor.execute('SELECT id FROM person WHERE name = ?', (person_name,))
                    person_id = cursor.fetchone()[0]

                    cursor.execute('SELECT id FROM person WHERE name = ?', (indirect_contact,))
                    indirect_contact_id = cursor.fetchone()[0]

                    # 使用當前時間作為接觸時間
                    contact_time = datetime.datetime.now().isoformat()

                    # 使用空字符串或預設值作為接觸地點
                    contact_location = ""  # 您可以根據需要指定一個地點

                    # 插入間接接觸
                    cursor.execute(''' 
                        INSERT OR IGNORE INTO contacts (person_id, contact_id, contact_type, source, contact_time, contact_location)
                        VALUES (?, ?, 'indirect', ?, ?, ?)''',
                        (person_id, indirect_contact_id, contact, contact_time, contact_location))

def generate_xml(person_dict, output_path):
    root = ET.Element("People")

    for person_name, person in person_dict.items():
        person_element = ET.SubElement(root, "Person", name=person.name)

        contacts_element = ET.SubElement(person_element, "Contacts")
        
        # 獲取直接接觸
        for contact in person.direct_contacts:
            ET.SubElement(contacts_element, "Contact", type="direct").text = contact

        # 獲取間接接觸
        for contact in person.indirect_contacts:
            ET.SubElement(contacts_element, "Contact", type="indirect").text = contact

    tree = ET.ElementTree(root)
    import xml.dom.minidom

    dom = xml.dom.minidom.parseString(ET.tostring(root, encoding='utf-8'))
    pretty_xml_as_string = dom.toprettyxml()

    with open(output_path, "w", encoding='utf-8') as fh:
        fh.write(pretty_xml_as_string)

def main():
    photo_folder = r"C:\Users\User\桌面\專題\database"
    output_folder = r"C:\Users\User\桌面\專題\detected_people"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 連接 SQLite 資料庫
    conn = sqlite3.connect('contacts.db')
    cursor = conn.cursor()
    create_tables(cursor)

    photos = [os.path.join(photo_folder, f) for f in os.listdir(photo_folder) if f.endswith(('jpg', 'jpeg', 'png'))]

    person_dict = {}

    for photo in photos:
        process_photo(photo, person_dict, output_folder, cursor)

    update_indirect_contacts(person_dict, cursor)

    # 生成 XML
    xml_output_path = os.path.join(os.path.dirname(photo_folder), "contacts.xml")
    generate_xml(person_dict, xml_output_path)

    print(f"XML file generated at: {xml_output_path}")

    # 提交變更並關閉資料庫連接
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
