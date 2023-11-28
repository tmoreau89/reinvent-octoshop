import streamlit as st
from octoai.client import Client
from octoai.errors import OctoAIClientError, OctoAIServerError
from io import BytesIO
from base64 import b64encode, b64decode
import requests
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

    if w > h:
        new_width = new_height = h
    else:
        new_width = new_height = w

    left = (w - new_width)/2
    top = (h - new_height)/2
    right = (w + new_width)/2
    bottom = (h + new_height)/2

    image = image.crop((left, top, right, bottom))

    image = image.resize((1024, 1024))
    return image


def octoshop(my_upload, meta_prompt):
    # Wrap all of this in a try block
    try:
        start = time.time()

        # UI columps
        colI, colO = st.columns(2)

        # Rotate image and perform some rescaling
        input_img = Image.open(my_upload)
        input_img = rotate_image(input_img)
        input_img = rescale_image(input_img)
        colI.write("Input image")
        colI.image(input_img)
        progress_text = "OctoShopping in action..."
        percent_complete = 0
        progress_bar = colO.progress(percent_complete, text=progress_text)

        # Number of images generated
        num_imgs = 1
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
        colO.write("OctoShopped images in {:.2f}s :star2:".format(end-start))
        for idx in range(num_imgs):
            results = oai_client.get_future_result(octoshop_futures[idx])
            octoshopped_image = Image.open(BytesIO(b64decode(results["images"][0])))
            if idx == 0:
                colI.text_area("", value=results["clip"])
            colO.image(octoshopped_image)
            colO.text_area("", value=results["story"])

    except OctoAIClientError as e:
        progress_bar.empty()
        colO.write("Oops something went wrong (client error)!")

    except OctoAIServerError as e:
        progress_bar.empty()
        colO.write("Oops something went wrong (server error)")

    except Exception as e:
        progress_bar.empty()
        colO.write("Oops something went wrong (unexpected error)!")


st.set_page_config(layout="wide", page_title="OctoShop")

st.write("## OctoShop - Powered by OctoAI")
st.write("\n\n")
st.write("### Transform photos with words!")

meta_prompt = st.text_input("Transformation Prompt", value="Set in 50s Las Vegas")

my_upload = st.camera_input("Take a snap")

if my_upload is not None:
    octoshop(my_upload, meta_prompt)
