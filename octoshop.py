import streamlit as st
from octoai.client import Client
from octoai.errors import OctoAIClientError, OctoAIServerError
from io import BytesIO
from base64 import b64encode, b64decode
from PIL import Image, ExifTags
import os
import time

OCTOSHOP_ENDPOINT_URL = os.environ["OCTOSHOP_ENDPOINT_URL"]
OCTOAI_TOKEN = os.environ["OCTOAI_TOKEN"]

# OctoAI client
oai_client = Client(OCTOAI_TOKEN)

def read_image(image):
    buffer = BytesIO()
    image.save(buffer, format="png")
    im_base64 = b64encode(buffer.getvalue()).decode("utf-8")
    return im_base64

def rotate_image(image):
    try:
        # Rotate based on Exif Data
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation]=='Orientation':
                break
        exif = image._getexif()
        if exif[orientation] == 3:
            image=image.rotate(180, expand=True)
        elif exif[orientation] == 6:
            image=image.rotate(270, expand=True)
        elif exif[orientation] == 8:
            image=image.rotate(90, expand=True)
        return image
    except:
        return image

def rescale_image(image):
    w, h = image.size

    if w == h:
        return image.resize((1024, 1024))
    else:
        if w > h:
            new_height = h
            new_width = int(h * 1216 / 832 )
        else:
            new_width = w
            new_height = int(w * 1216 / 832)

        left = (w - new_width)/2
        top = (h - new_height)/2
        right = (w + new_width)/2
        bottom = (h + new_height)/2
        image = image.crop((left, top, right, bottom))

        if w > h:
            return image.resize((1216, 832))
        else:
            return image.resize((832, 1216))

def octoshop(my_upload, meta_prompt):
    # Wrap all of this in a try block
    try:
        start = time.time()

        # Rotate image and perform some rescaling
        input_img = Image.open(my_upload)
        input_img = rotate_image(input_img)
        input_img = rescale_image(input_img)
        progress_text = "OctoShopping in action..."
        percent_complete = 0
        progress_bar = st.progress(percent_complete, text=progress_text)

        # Number of images generated
        num_imgs = 4
        octoshop_futures = {}
        for idx in range(num_imgs):
            # Query endpoint async
            octoshop_futures[idx] = oai_client.infer_async(
                f"{OCTOSHOP_ENDPOINT_URL}/generate",
                {
                    "prompt": meta_prompt,
                    "batch": 1,
                    "strength": 0.33,
                    "steps": 20,
                    "sampler": "K_EULER_ANCESTRAL",
                    "image": read_image(input_img),
                    "faceswap": True,
                    "style": "photographic",
                    "octoai": False
                }
            )

        # Poll on completion - target 30s completion - hence the 0.25 time step
        finished_jobs = {}
        time_step = 0.25
        while len(finished_jobs) < num_imgs:
            time.sleep(time_step)
            percent_complete = min(99, percent_complete+1)
            if percent_complete == 99:
                progress_text = "OctoShopping is taking longer than usual, hang tight!"
            progress_bar.progress(percent_complete, text=progress_text)
            # Update completed jobs
            for idx, future in octoshop_futures.items():
                if idx not in finished_jobs:
                    if oai_client.is_future_ready(future):
                        finished_jobs[idx] = "done"

        # Process results
        end = time.time()
        progress_bar.empty()
        st.write("OctoShopped images in {:.2f}s :star2:".format(end-start))
        col0, col1 = st.columns(2)
        for idx in range(num_imgs):
            results = oai_client.get_future_result(octoshop_futures[idx])
            octoshopped_image = Image.open(BytesIO(b64decode(results["images"][0])))
            if idx % 2 == 0:
                col0.image(octoshopped_image)
                col0.text_area("Llama2 describes:", value=results["story"])
            elif idx % 2 == 1:
                col1.image(octoshopped_image)
                col1.text_area("Llama2 describes:", value=results["story"])

    except OctoAIClientError as e:
        progress_bar.empty()
        st.write("Oops something went wrong (client error)!")

    except OctoAIServerError as e:
        progress_bar.empty()
        st.write("Oops something went wrong (server error)")

    except Exception as e:
        progress_bar.empty()
        st.write("Oops something went wrong (unexpected error)!")


st.set_page_config(layout="wide", page_title="OctoShop - Holiday edition")

st.write("## Ugly xmas sweater generator")
st.write("\n\n")
st.write("### For OctoML internal use only! Something fun to play with ahead of the holidays...")

# meta_prompt = st.text_input("Transformation Prompt", value="Set in 50s Las Vegas")
meta_prompt = "set in an ugly christmas sweater competition"

my_upload = st.file_uploader("Take a snap or upload a photo", type=["png", "jpg", "jpeg"])

if my_upload is not None:
    if st.button('OctoShop!'):
        octoshop(my_upload, meta_prompt)
