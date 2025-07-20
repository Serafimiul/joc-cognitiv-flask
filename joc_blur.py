from flask import Flask, render_template, request, redirect, url_for, session
import os
import cv2
import time
import csv
import base64
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "secret_key"

# Configurări
IMAGE_FOLDER = "static/images"
CSV_PATH = os.path.join("data", "scoruri.csv")
os.makedirs("data", exist_ok=True)
os.makedirs("static/graphs", exist_ok=True)

CORRECT_ANSWERS = {
    "pisica.jpg": "pisica",
    "cheie.jpg": "cheie",
    "mar.png": "mar"
}

BLUR_LEVELS = [31, 21, 11, 5, 1]

# Functie pentru blur
def blur_image(cv_img, ksize):
    if ksize <= 1:
        return cv_img.copy()
    return cv2.GaussianBlur(cv_img, (ksize, ksize), 0)

# Conversie imagine OpenCV -> base64
def convert_to_base64(cv_img):
    rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb_img)
    buffer = BytesIO()
    pil_img.save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded

# Interpretare scor
def interpret_score(score):
    if score >= 90:
        return "Recunoastere excelenta"
    elif score >= 70:
        return "Recunoastere buna"
    elif score >= 40:
        return "Intarziere moderata"
    else:
        return "Dificultate semnificativa"

# Salvare scor
def save_result(image_name, blur_level, time_elapsed, user_guess, score, interpretation):
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Imagine", "Nivel blur", "Timp (sec)", "Raspuns", "Scor", "Interpretare"])
        writer.writerow([image_name, blur_level, f"{time_elapsed:.2f}", user_guess, score, interpretation])


# Generare grafice
def generate_graphs():
    durations = []
    labels = []
    blur_times = defaultdict(list)

    with open(CSV_PATH, newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Timp (sec)"] != "n/a":
                durations.append(float(row["Timp (sec)"]))
                labels.append(row["Imagine"])
                blur_level = row["Nivel blur"]
                if blur_level != "n/a":
                    blur_times[int(blur_level)].append(float(row["Timp (sec)"]))

    # Grafic 1: Timp per imagine
    plt.figure(figsize=(10, 5))
    plt.plot(range(1, len(durations) + 1), durations, marker='o', linestyle='-')
    plt.title("Timp raspuns per imagine")
    plt.xlabel("Nr. imagine")
    plt.ylabel("Durata (secunde)")
    plt.grid(True)
    plt.savefig("static/graphs/timp_pe_imagine.png")
    plt.close()

    # Grafic 2: Timp mediu per blur
    blur_levels = sorted(blur_times.keys())
    avg_durations = [sum(times)/len(times) for times in [blur_times[k] for k in blur_levels]]

    plt.figure(figsize=(10, 5))
    plt.bar([str(k) for k in blur_levels], avg_durations, color="orange")
    plt.title("Timp mediu per nivel de blur")
    plt.xlabel("Nivel blur")
    plt.ylabel("Durata medie (secunde)")
    plt.grid(axis='y')
    plt.savefig("static/graphs/timp_pe_blur.png")
    plt.close()

# Pagina principala
@app.route('/')
def index():
    session.clear()
    session["images"] = list(CORRECT_ANSWERS.keys())
    session["current"] = 0
    session["score"] = 0
    return render_template("index.html")

# Pagina de joc
@app.route('/game', methods=["GET", "POST"])
def game():
    images = session.get("images", [])
    current_index = session.get("current", 0)
    score = session.get("score", 0)

    if current_index >= len(images):
        generate_graphs()
        average_score = score / len(images)
        interpretation = interpret_score(average_score)
        return render_template("result.html", score=average_score, interpretation=interpretation)

    image_name = images[current_index]
    correct_answer = CORRECT_ANSWERS[image_name]
    image_path = os.path.join(IMAGE_FOLDER, image_name)
    original_image = cv2.imread(image_path)

    if "start_time" not in session:
        session["start_time"] = time.time()
        session["blur_index"] = 0

    if request.method == "POST":
        guess = request.form.get("guess", "").strip()
        blur_level = BLUR_LEVELS[session["blur_index"]]
        time_elapsed = time.time() - session["start_time"]

        if correct_answer.lower() in guess.lower():
            current_score = 100 - (session["blur_index"] * 20)
            interpretation = interpret_score(current_score)
            save_result(image_name, blur_level, time_elapsed, guess, current_score, interpretation)
            session["score"] = score + current_score
            session["current"] = current_index + 1
            session.pop("start_time", None)
            session.pop("blur_index", None)
            return redirect(url_for("game"))
        else:
            session["blur_index"] += 1
            if session["blur_index"] >= len(BLUR_LEVELS):
                save_result(image_name, "n/a", time_elapsed, guess, 0, "Fara raspuns corect")
                session["current"] = current_index + 1
                session.pop("start_time", None)
                session.pop("blur_index", None)
                return redirect(url_for("game"))

    blur_level = BLUR_LEVELS[session["blur_index"]]
    blurred_image = blur_image(original_image, blur_level)
    image_data = convert_to_base64(blurred_image)
    return render_template("game.html", image_data=image_data)

# Pornim serverul
if __name__ == '__main__':
    app.run(debug=True)
