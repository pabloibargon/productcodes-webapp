from flask import Flask, request, render_template, redirect, url_for
from PIL import Image
import os
import base64

import product_codes

app = Flask(__name__)

if __name__ == "__main__":
    app.run(debug=True)
    
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["FILENAME_FOR_ORIGINAL"] = "original"
app.config["FILENAME_FOR_CORRUPTED"] = "corrupted.png"
app.config["FILENAME_FOR_CORRECTED"] = product_codes.FILENAME_FOR_CORRECTED
app.config["FILENAME_FOR_ENCODED"] = product_codes.FILENAME_FOR_ENCODED
app.config["FILENAME_FOR_TEMP"] = product_codes.FILENAME_FOR_TEMP


# TODO hard-coded partial results filename


ALLOWED_EXTENSIONS = ["jpg","png"]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def hello():
    return render_template("base.html")


@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    if request.method == "POST":
        # check if the post request has the file part
        if "image" not in request.files:
            return render_template("error.html", message="---", url=request.url)
        file = request.files["image"]
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == "":
            return render_template(
                "error.html", message="Archivo no seleccionado", url=request.url
            )
        if file and allowed_file(file.filename):
            filename = file.filename
            split = filename.rsplit(".", 1)
            filename = split[0]
            extension = split[1]

            # Every image resulting from the uploaded image will be saved in /uploads/filename/
            image_dir = os.path.join(app.static_folder, app.config["UPLOAD_FOLDER"])
            
            #try creating uploads folder if not exist
            try:
                os.mkdir(image_dir)
            except:
                pass

            image_dir = os.path.join(
                image_dir, filename
            )  # dir name filename wo extension
            try:
                os.mkdir(image_dir)
            except:
                print('overwriting directory ...')
                try:
                    os.remove(os.path.join(image_dir,app.config["FILENAME_FOR_TEMP"]))
                    print('removed temp file')
                except:
                    print('no previous temp file found')

            image_path = os.path.join(
                image_dir, app.config["FILENAME_FOR_ORIGINAL"] + "." + extension
            )
            file.save(image_path)
            product_codes.encode_image_from_path(image_path, image_dir)

            return redirect(url_for("show_image", filename=filename))
    return render_template("upload.html")


@app.route("/show_image/<filename>")
def show_image(filename):
    temp_file = None
    # sin static porque en la plantilla se usa url_for(static,) para eso
    image_dir = os.path.join(
        app.config["UPLOAD_FOLDER"], filename
    )  # dir name filename wo extension
    try:
        original_file = [
            filename
            for filename in os.listdir(os.path.join(app.static_folder, image_dir))
            if filename.startswith(app.config["FILENAME_FOR_ORIGINAL"])
        ][0]
    except:
        return render_template(
            "error.html", message="La imagen buscada no existe", url="/"
        )
    try:
        temp_file = [
            filename
            for filename in os.listdir(os.path.join(app.static_folder, image_dir))
            if filename.startswith(app.config["FILENAME_FOR_TEMP"])
        ][0]
        temp_file = os.path.join(image_dir,temp_file)
    except:
        pass
    encoded_file = os.path.join(image_dir, app.config["FILENAME_FOR_ENCODED"])
    return render_template("show_image.html", filename=temp_file or encoded_file, reset = encoded_file)


@app.route("/save_image/<filename>", methods=["POST"])
def save_image(filename):
    try:
        im = request.form.get("image")
    except:
        print("not in form")
        return "error"

    im = im.removeprefix("data:image/png;base64,")
    base64_bytes = im.encode("ascii")
    im_bytes = base64.b64decode(base64_bytes)
    im_path = os.path.join(app.static_folder, app.config["UPLOAD_FOLDER"])
    im_path = os.path.join(im_path, filename)
    im_path = os.path.join(im_path, app.config["FILENAME_FOR_CORRUPTED"])
    with open(im_path, "wb") as f:
        f.write(im_bytes)
    return "image saved on server"

@app.route("/noise/<filename>", methods=["POST"])
def noise(filename):
    try:
        im = request.form.get("image")
    except:
        print("not in form")
        return "error"

    im = im.removeprefix("data:image/png;base64,")
    base64_bytes = im.encode("ascii")
    im_bytes = base64.b64decode(base64_bytes)
    im_dir = os.path.join(app.static_folder, app.config["UPLOAD_FOLDER"])
    im_dir = os.path.join(im_dir, filename)
    im_path = os.path.join(im_dir, app.config["FILENAME_FOR_TEMP"])
    with open(im_path, "wb") as f:
        f.write(im_bytes)
    #corrupt
    product_codes.add_random_noise_from_path(im_path,im_dir,int(request.form.get("density"))/100)
    return "image saved on server"

@app.route("/show_result/<filename>")
def show_result(filename):
    image_dir = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image_dir_w_static = os.path.join(app.static_folder, image_dir)
    corrupted_path = os.path.join(
        image_dir_w_static, app.config["FILENAME_FOR_CORRUPTED"]
    )
    # try:
    product_codes.naive_decode_image_from_path(corrupted_path, image_dir_w_static)
    # except Exception:
    #     print(Exception.message)
    #     return render_template(
    #         "error.html", message="La imagen buscada no existe", url="/"
    #     )
    corrupted_path = os.path.join(image_dir, app.config["FILENAME_FOR_CORRUPTED"])
    corrected_rows_path = os.path.join(image_dir, "corrected_rows.png")
    corrected_path = os.path.join(image_dir, app.config["FILENAME_FOR_CORRECTED"])
    return render_template(
        "show_result.html",
        corrupted_path=corrupted_path,
        corrected_rows_path=corrected_rows_path,
        corrected_path=corrected_path,
    )
