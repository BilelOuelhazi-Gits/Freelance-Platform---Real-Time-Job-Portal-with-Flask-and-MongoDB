from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session
import os
from bson import ObjectId
from datetime import datetime
from flask import send_from_directory
from flask_socketio import SocketIO, emit




app = Flask(__name__)

app.config["MONGO_URI"] = "mongodb://localhost:27017/JOB"
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SESSION_TYPE"] = "filesystem"
socketio = SocketIO(app)
UPLOAD_FOLDER = 'uploads'
app.config["UPLOAD_FOLDER"] = "uploads"



@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

mongo = PyMongo(app)
Session(app)





@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")


        if mongo.db.users.find_one({"email": email}):
            flash("Email already registered!", "danger")
            return redirect(url_for("register"))


        hashed_password = generate_password_hash(password)

        mongo.db.users.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password,
            "role": role,
            "profile_complete": False
        })

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = mongo.db.users.find_one({"email": email})

        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            session["role"] = user["role"]

            flash("Login successful!", "success")

            if user["role"] == "Applier":

                if not user.get("profile_complete"):
                    return redirect(url_for("complete_profile"))
                return redirect(url_for("applier_dashboard"))
            elif user["role"] == "Poster":
                return redirect(url_for("poster_dashboard"))

        flash("Invalid email or password", "danger")

    return render_template("login.html")


@app.route("/complete_profile", methods=["GET", "POST"])
def complete_profile():
    if "user_id" not in session or session["role"] != "Applier":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    user = mongo.db.users.find_one({"_id": ObjectId(session["user_id"])})

    if user.get("profile_complete"):
        return redirect(url_for("applier_dashboard"))

    if request.method == "POST":

        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        address = request.form.get("address")
        linkedin = request.form.get("linkedin")
        portfolio = request.form.get("portfolio")

        education = {
            "level": request.form.get("education_level"),
            "university": request.form.get("university"),
            "field_of_study": request.form.get("field_of_study"),
            "graduation_year": request.form.get("graduation_year"),
            "certifications": request.form.getlist("certifications")
        }

        work_experience = {
            "company": request.form.get("company"),
            "job_title": request.form.get("job_title"),
            "years_experience": request.form.get("years_experience"),
            "industry": request.form.get("industry"),
            "projects": request.form.get("projects")
        }

        job_preferences = {
            "job_type": request.form.get("job_type"),
            "salary_range": request.form.get("salary_range"),
            "work_location": request.form.get("work_location"),
            "availability": request.form.get("availability")
        }


        cv = request.files.get("cv")
        profile_pic = request.files.get("profile_picture")
        cover_letter = request.files.get("cover_letter")

        cv_path = os.path.join(app.config["UPLOAD_FOLDER"], cv.filename) if cv else None
        profile_pic_path = os.path.join(app.config["UPLOAD_FOLDER"], profile_pic.filename) if profile_pic else None
        cover_letter_path = os.path.join(app.config["UPLOAD_FOLDER"], cover_letter.filename) if cover_letter else None


        if cv:
            cv.save(cv_path)
        if profile_pic:
            profile_pic.save(profile_pic_path)
        if cover_letter:
            cover_letter.save(cover_letter_path)


        mongo.db.users.update_one(
            {"_id": ObjectId(session["user_id"])},
            {"$set": {
                "full_name": full_name,
                "phone": phone,
                "address": address,
                "linkedin": linkedin,
                "portfolio": portfolio,
                "education": education,
                "work_experience": work_experience,
                "job_preferences": job_preferences,
                "cv": cv_path,
                "profile_picture": profile_pic_path,
                "cover_letter": cover_letter_path,
                "profile_complete": True
            }}
        )

        flash("Profile updated successfully!", "success")
        return redirect(url_for("applier_dashboard"))

    return render_template("complete_profile.html")





@app.route("/post_job", methods=["POST"])
def post_job():
    if "user_id" not in session or session.get("role") != "Poster":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    # Gather form data (example, adjust to your form fields)
    job_title = request.form.get("job_title")
    location = request.form.get("location")
    job_type = request.form.get("job_type")
    salary_range = request.form.get("salary_range")
    skills_required = request.form.getlist("skills_required")
    deadline = request.form.get("deadline")
    job_description = request.form.get("job_description")

    job_data = {
        "job_title": job_title,
        "location": location,
        "job_type": job_type,
        "salary_range": salary_range,
        "skills_required": skills_required,
        "deadline": deadline,
        "job_description": job_description,
        "poster_id": session["user_id"],
    }

    mongo.db.jobs.insert_one(job_data)

    # Emit notification to all connected applier clients
    socketio.emit("new_job_posted", {
        "job_title": job_title,
        "location": location,
        "job_type": job_type
    })

    flash("Job posted successfully!", "success")
    return redirect(url_for("poster_dashboard"))




@app.route("/delete_job/<job_id>")
def delete_job(job_id):
    if "user_id" not in session or session["role"] != "Poster":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))


    mongo.db.jobs.delete_one({"_id": ObjectId(job_id)})

    flash("Job deleted successfully!", "success")
    return redirect(url_for("poster_dashboard"))




@app.route("/applier")
def applier_dashboard():
    if "user_id" not in session or session["role"] != "Applier":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    # Get all jobs
    all_jobs = list(mongo.db.jobs.find())

    # Get applied job ids
    applied_jobs = mongo.db.applications.find({"applier_id": session["user_id"]})
    applied_job_ids = {app["job_id"] for app in applied_jobs}

    return render_template("applier.html", username=session["username"], jobs=all_jobs, applied_job_ids=applied_job_ids)



@app.route("/")
def Home():
    all_jobs = list(mongo.db.jobs.find())
    # no applied_jobs on server for visitors without account
    return render_template("home.html", jobs=all_jobs)






@app.route("/apply/<job_id>", methods=["GET", "POST"])
def apply_job(job_id):
    if "user_id" not in session or session["role"] != "Applier":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    # Show form to write cover letter
    if request.method == "GET":
        job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
        return render_template("submit_application.html", job=job)

    # Handle form submission
    cover_letter = request.form.get("cover_letter")

    existing_application = mongo.db.applications.find_one({
        "applier_id": session["user_id"],
        "job_id": job_id
    })

    if existing_application:
        flash("You have already applied to this job.", "warning")
    else:
        mongo.db.applications.insert_one({
            "applier_id": session["user_id"],
            "job_id": job_id,
            "applied_on": datetime.now(),
            "status": "Pending",
            "cover_letter": cover_letter
        })
        flash("Successfully applied to job!", "success")

    return redirect(url_for("applier_dashboard"))



@app.route("/poster")
def poster_dashboard():
    if "user_id" not in session or session["role"] != "Poster":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))


    jobs = mongo.db.jobs.find({"poster_id": session["user_id"]})

    return render_template("poster.html", username=session["username"], jobs=jobs)


@app.route("/chat/<job_id>/<applier_id>", methods=["GET", "POST"])
def chat(job_id, applier_id):
    if "user_id" not in session:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for("poster_dashboard"))

    # Authorization: must be the poster or the applier
    if session["user_id"] not in [job["poster_id"], applier_id]:
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    # Determine user role
    user_role = "poster" if session["user_id"] == job["poster_id"] else "applier"

    # Handle new message
    if request.method == "POST":
        message = request.form.get("message")
        if message.strip():
            mongo.db.messages.insert_one({
                "job_id": job_id,
                "applier_id": applier_id,
                "poster_id": job["poster_id"],
                "sender": session["user_id"],
                "message": message,
                "timestamp": datetime.now()
            })

            # Emit to relevant users (poster and applier)
            socketio.emit("new_message", {
                "job_id": job_id,
                "applier_id": applier_id,
                "poster_id": job["poster_id"],
                "sender": session["user_id"],
                "message": message,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M')
            })

            return redirect(url_for("chat", job_id=job_id, applier_id=applier_id))

    # Load messages
    messages = mongo.db.messages.find({
        "job_id": job_id,
        "applier_id": applier_id
    }).sort("timestamp", 1)

    messages_list = list(messages)
    applier = mongo.db.users.find_one({"_id": ObjectId(applier_id)})
    poster = mongo.db.users.find_one({"_id": ObjectId(job["poster_id"])})

    return render_template("chat.html",
                           job=job,
                           messages=messages_list,
                           applier=applier,
                           poster=poster,
                           current_user=session["user_id"],
                           user_role=user_role)




@app.route("/chat/messages/<job_id>/<applier_id>")
def chat_messages(job_id, applier_id):
    messages = mongo.db.messages.find({
        "job_id": job_id,
        "applier_id": applier_id
    }).sort("timestamp", 1)

    # Return messages as JSON
    message_list = [{
        "sender": msg["sender"],
        "message": msg["message"],
        "timestamp": msg["timestamp"].strftime('%Y-%m-%d %H:%M')
    } for msg in messages]

    return jsonify(message_list)


@app.route("/job_applications/<job_id>")
def view_applications(job_id):
    if "user_id" not in session or session["role"] != "Poster":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})

    if not job or job["poster_id"] != session["user_id"]:
        flash("You are not authorized to view these applications.", "danger")
        return redirect(url_for("poster_dashboard"))

    applications = list(mongo.db.applications.find({"job_id": job_id}))
    for app in applications:
        user = mongo.db.users.find_one({"_id": ObjectId(app["applier_id"])})
        app["applier_name"] = user.get("full_name", "Unknown")
        app["email"] = user.get("email")
        app["cv"] = user.get("cv")
        app["profile_picture"] = user.get("profile_picture")

    return render_template("job_applications.html", job=job, applications=applications)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))





if __name__ == "__main__":
    socketio.run(app, debug=True)