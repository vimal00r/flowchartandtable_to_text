import os
import fitz
import io
import pdfplumber
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from Flowchart_to_text.flowchart_to_text import *
# from flowchart_to_text import *

output_dir=".\\Flowchart_to_text\\all_images"
output_format="png"

model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")


def extract_flowchart_images_from_pdf(pdf_file_path, min_width=100, min_height=100):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pdf_file = fitz.open(pdf_file_path)
    saved_image_paths = []
    flow_index = []

    for page_index in range(len(pdf_file)):
        page = pdf_file[page_index]
        image_list = page.get_images(full=True)

        for image_index, img in enumerate(image_list, start=1):
            xref = img[0]
            base_image = pdf_file.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image = Image.open(io.BytesIO(image_bytes))

            if image.width >= min_width and image.height >= min_height:
                save_path = os.path.join(output_dir, f"Page-{page_index+1} Image-{image_index}.{output_format}")
                image.save(open(save_path, "wb"), format=output_format.upper())
                saved_image_paths.append(save_path)
            else:
                print(f"[-] Skipping image {image_index} on page {page_index+1} due to its small size.")

    file_list = os.listdir("./Flowchart_to_text/all_images")
    filtered_image_paths = []

    for image_path in file_list:
        image = Image.open("./Flowchart_to_text/all_images/"+image_path)
        inputs = processor(text=["flowchart", "table"], images=image, return_tensors="pt", padding=True)
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image
        probs = logits_per_image.softmax(dim=1)
        confidence_score = probs[0][0].item()
        if confidence_score >= 0.8:
            filtered_image_paths.append(image_path)
    return filtered_image_paths


def pdf_redact(doc, page_num, rectangle, text):
    doc[page_num].add_redact_annot(rectangle)
    doc[page_num].apply_redactions()
    tw = fitz.TextWriter(doc[page_num].rect)
    tw.fill_textbox(rectangle, text)
    tw.write_text(doc[page_num])


def flowchart_to_text(file_path):
    pdf_file = fitz.open(file_path)
    flowchart_id_dict = {}
    for page_num in range(len(pdf_file)):
        page_content = pdf_file[page_num]
        images = page_content.get_images(full = True)
        for c, image_info in enumerate(images, start=1):
            xref = image_info[0]
            base_image = pdf_file.extract_image(xref)
            image_bytes = base_image['image']
            image_ext = base_image['ext']

            image_name = f"Page-{page_num+1} Image-{c}.{output_format}"

            pdf_obj = pdfplumber.open(file_path)
            page = pdf_obj.pages[page_num]
            images_in_page = page.images
            page_height = page.height

            if images_in_page:
                count = 0
                for image in images_in_page:
                    image_bbox = (image['x0'], page_height - image['y1'], image['x1'], page_height - image['y0'])
                    pdf_redact(pdf_file, page_num, fitz.Rect(image_bbox), f"Page-{page_num+1} Image-{count+1}" )
                    
                    if image_name in extract_flowchart_images_from_pdf(file_path):
                        text = flowchart_image_to_text("./Flowchart_to_text/all_images/"+image_name)
                        flowchart_id_dict[image_name.split(".")[0]] = str(text)
                    else:
                        flowchart_id_dict[image_name.split(".")[0]] = "Not a Flowchart. It's an image"

                    count += 1


    pdf_file.save('./flowchart_to_text_output.pdf', deflate=True)
    pdf_file.close()

    return flowchart_id_dict
#     print(flowchart_id_dict)
# flowchart_to_text('table_to_text.pdf')

