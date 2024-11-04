import face_recognition
import os
import xml.etree.ElementTree as ET
from PIL import Image

class Person:
    def __init__(self, name, face_encoding):
        self.name = name
        self.face_encoding = face_encoding
        self.direct_contacts = set()
        self.indirect_contacts = set()
        self.indirect_contacts_with_source = {}  # 新增：存放間接接觸者和來源的字典

def process_photo(photo_path, person_dict, output_folder):
    # 讀取照片
    img = face_recognition.load_image_file(photo_path)
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    current_photo_people = []

    for face_location, face_encoding in zip(face_locations, face_encodings):
        matched_person = None
        # 檢查新出現的每個人物是否與已識別人物相符
        for person_name, person in person_dict.items():
            match_results = face_recognition.compare_faces([person.face_encoding], face_encoding)
            if match_results[0]:  # 如果比對成功，則為同一個人
                matched_person = person_name
                break

        if matched_person:
            current_photo_people.append(matched_person)
        else:
            # 如果沒匹配上，新增一個新的人物
            new_person_name = f"Person_{len(person_dict) + 1}"
            person_dict[new_person_name] = Person(new_person_name, face_encoding)
            current_photo_people.append(new_person_name)

            # 保存新人物的臉部圖片
            top, right, bottom, left = face_location
            face_image = img[top:bottom, left:right]
            pil_image = Image.fromarray(face_image)
            person_image_path = os.path.join(output_folder, f"{new_person_name}.jpg")
            pil_image.save(person_image_path)
            print(f"Saved face image for {new_person_name} at {person_image_path}")

    # 記錄直接接觸
    for i in range(len(current_photo_people)):
        for j in range(len(current_photo_people)):
            if i != j:
                person_dict[current_photo_people[i]].direct_contacts.add(current_photo_people[j])

    return current_photo_people

def generate_xml(person_dict, output_path):
    root = ET.Element("People")

    for person_name, person in person_dict.items():
        person_element = ET.SubElement(root, "Person", name=person.name)

        # 直接接觸
        direct_contacts_element = ET.SubElement(person_element, "DirectContacts")
        for contact in person.direct_contacts:
            ET.SubElement(direct_contacts_element, "Contact").text = contact

        # 間接接觸
        indirect_contacts_element = ET.SubElement(person_element, "IndirectContacts")
        for contact, source in person.indirect_contacts_with_source.items():
            ET.SubElement(indirect_contacts_element, "Contact").text = f"{contact} (through {source})"

    # 美化 XML
    tree = ET.ElementTree(root)
    import xml.dom.minidom

    dom = xml.dom.minidom.parseString(ET.tostring(root, encoding='utf-8'))
    pretty_xml_as_string = dom.toprettyxml()

    # 寫入美化後的 XML
    with open(output_path, "w", encoding='utf-8') as fh:
        fh.write(pretty_xml_as_string)

def update_indirect_contacts(person_dict):
    # 更新間接接觸
    for person_name, person in person_dict.items():
        all_direct_contacts = person.direct_contacts.copy()
        for contact in all_direct_contacts:
            for indirect_contact in person_dict[contact].direct_contacts:
                if indirect_contact != person_name and indirect_contact not in person.direct_contacts:
                    person.indirect_contacts.add(indirect_contact)
                    person.indirect_contacts_with_source[indirect_contact] = contact  # 新增：記錄來源
        # 移除自己
        person.indirect_contacts.discard(person_name)

def main():
    # 定義照片資料夾路徑
    photo_folder = r"C:\Users\User\桌面\專題\database"

    # 定義輸出資料夾
    output_folder = r"C:\Users\User\桌面\專題\detected_people"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 讀取資料夾中的所有照片
    photos = [os.path.join(photo_folder, f) for f in os.listdir(photo_folder) if f.endswith(('jpg', 'jpeg', 'png'))]

    person_dict = {}

    for photo in photos:
        process_photo(photo, person_dict, output_folder)

    # 更新間接接觸
    update_indirect_contacts(person_dict)

    # 生成 XML
    xml_output_path = os.path.join(os.path.dirname(photo_folder), "contacts.xml")
    generate_xml(person_dict, xml_output_path)

    print(f"XML file generated at: {xml_output_path}")

if __name__ == "__main__":
    main()
