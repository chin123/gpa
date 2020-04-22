from flask import Flask, render_template, request
import pandas as pd
import matplotlib.pyplot as plt
import base64
import io
import hashlib
import time
import numpy as np

app = Flask(__name__)

df = pd.read_csv("uiuc-gpa-dataset.csv")
grades = []
for i in df.columns:
    if len(i) < 3:
        grades.append(i)

#remove the W
grades = grades[:len(grades)-1]
weight = [4.00, 4.00, 3.67, 3.33, 3, 2.67, 2.33, 2, 1.67, 1.33, 1, 0.67, 0]
semesters = []
sem_full_form = {'sp': "Spring", 'fa': "Fall", 'su': "Summer", 'wi': "Winter"}

cross = pd.read_csv("cross.txt", names=['cross', 'orig'])

for i in df["YearTerm"].unique():
    fullname = sem_full_form[i.split('-')[1]] + " " + i.split('-')[0]
    semesters.append({'value': i, 'text': fullname, 'selected': False})


def errmsg(msg):
    return render_template("index.html", err=msg, semesters=semesters, prevcourse=request.form["course"])

@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method=="POST":
        imgpath = "/static/images/plot.png"

        # Obtain data from form and validate
        course = request.form["course"].split()
        prevcourse = request.form["course"]
        if len(course) != 2:
            return errmsg("Invalid format. Must be of the form SUBJECT COURSENUM")

        subj, num = course[0], course[1]
        if not num.isdigit():
            return errmsg("Course number invalid")

        num = int(num)
        subj = subj.upper()

        orig = cross[cross["cross"] == subj + " " + str(num)]
        if len(orig) != 0:
            subj = orig["orig"].iloc[0].split()[0]
            num = int(orig["orig"].iloc[0].split()[1])

        course_stats = df[df["Subject"] == subj][df["Number"] == num]
        if len(course_stats) == 0:
          return errmsg("No such course found")

        semester = request.form["semester"]
        if semester != "All":
            course_stats = course_stats[course_stats["YearTerm"] == semester]

        for i in range(len(semesters)):
            semesters[i]['selected'] = False
            if semesters[i]['value'] == semester:
                semesters[i]['selected'] = True

        if len(course_stats) == 0:
          return errmsg("Course not found in specified semester")

        # Calculate average GPA
        num_students_total = course_stats[grades].sum().sum()
        gpa_sum = 0
        ind = 0
        for i in course_stats[grades].sum():
            gpa_sum += weight[ind]*i
            ind += 1
        avg_gpa_total = gpa_sum/num_students_total

        # Calculate avg gpa per instructor
        grade_prof_col = grades + ["Primary Instructor"]
        prof_stats_df = course_stats[grade_prof_col].groupby("Primary Instructor").sum()
        prof_stats = []
        for index, row in prof_stats_df.iterrows():
            num_students = row[grades].sum()
            ind = 0
            gpas = []
            for i in row[grades]:
                for j in range(i):
                    gpas.append(weight[ind])
                ind += 1
            gpas = np.array(gpas)
            avg_gpa = gpas.mean()
            std_gpa = gpas.std()
            prof_stats.append({'prof': row.name, 'total': num_students, 'avg': '%.3f'%avg_gpa, 'std': '%.3f'%std_gpa})
        prof_stats = sorted(prof_stats, key=lambda k: k['avg'], reverse=True)



        # Create grade distribution plot
        course_stats[grades].sum().plot(kind='bar')

        pic_IObytes = io.BytesIO()
        plt.savefig(pic_IObytes, format='png')
        pic_IObytes.seek(0)

        BLOCKSIZE = 65536
        hasher = hashlib.sha1()
        buf = pic_IObytes.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = pic_IObytes.read(BLOCKSIZE)
        pic_hash = hasher.hexdigest()
        fname = 'static/images/' + pic_hash + '.png'

        plt.savefig(fname)
        plt.clf()

        # Calculate % of students in each grade
        perc = []
        for (g,n) in zip(grades, course_stats[grades].sum()):
            perc.append({'g': g, 'p': '%.3f'%((n/num_students_total)*100)})

        if semester == "All":
            semester_msg = "All Semesters"
        else:
            semester_msg = sem_full_form[semester.split('-')[1]] + " " + semester.split('-')[0]

        return render_template("index.html", img=pic_hash + '.png', gpa='%.3f'%avg_gpa_total, perc=perc, prof_stats=prof_stats, semesters=semesters
        , course=request.form["course"].upper(), semester=semester_msg, prevcourse=prevcourse)
    return render_template("index.html", semesters=semesters)
    
if __name__ == "__main__":
    app.run(debug=True)
