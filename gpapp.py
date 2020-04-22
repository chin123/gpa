from flask import Flask, render_template, request
import pandas as pd
import matplotlib.pyplot as plt
import base64
import io
import hashlib
import urllib
import html
import numpy as np

def errmsg(msg):
    return render_template("index.html", err=msg, semesters=semesters, prevcourse=request.args["course"], filters=FILTERS)

def get_grades(df):
    grades = []
    for i in df.columns:
        if len(i) < 3:
            grades.append(i)
    #remove the W
    grades = grades[:len(grades)-1]
    return grades

def get_semesters(df):
    semesters = []
    for i in df["YearTerm"].unique():
        fullname = SEM_FULL_FORM[i.split('-')[1]] + " " + i.split('-')[0]
        semesters.append({'value': i, 'text': fullname, 'selected': False})

    return semesters

def validate_course(course):
    if len(course) != 2:
        return False, "Invalid format. Must be of the form SUBJECT COURSENUM"

    subj, num = course[0], course[1]
    if not num.isdigit():
        return False, "Course number invalid"

    return True, "Valid Request"

def get_subj_and_num(course):
    subj, num = course[0], course[1]
    num = int(num)
    subj = subj.upper()
    return subj, num

def get_avg_gpa(course_stats):
    ind = 0
    gpas = []
    for i in course_stats[grades].sum():
        for j in range(i):
            gpas.append(WEIGHT[ind])
        ind += 1
    gpas = np.array(gpas)
    return gpas.mean(), gpas.std()

def get_prof_stats(course_stats):
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
                gpas.append(WEIGHT[ind])
            ind += 1
        gpas = np.array(gpas)
        avg_gpa = gpas.mean()
        std_gpa = gpas.std()
        prof_stats.append({'prof': row.name, 'total': num_students, 'avg': '%.3f'%avg_gpa, 'std': '%.3f'%std_gpa})
    prof_stats = sorted(prof_stats, key=lambda k: k['avg'], reverse=True)
    return prof_stats

def gen_plot(course_stats):
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
    return pic_hash

def get_perc(course_stats):
    # Calculate % of students in each grade
    perc = []
    num_students_total = course_stats[grades].sum().sum()
    for (g,n) in zip(grades, course_stats[grades].sum()):
        perc.append({'g': g, 'p': '%.3f'%((n/num_students_total)*100)})
    return perc

def get_semester_msg(semester):
    if semester == "All":
        semester_msg = "All Semesters"
    else:
        semester_msg = SEM_FULL_FORM[semester.split('-')[1]] + " " + semester.split('-')[0]
    return semester_msg

def mark_selected_semesters(semester):
    for i in range(len(semesters)):
        semesters[i]['selected'] = False
        if semesters[i]['value'] == semester:
            semesters[i]['selected'] = True

    return semesters

def search_course(df, regex):
    shortlist = df[df["CourseFull"].str.contains(regex)]["CourseFull"].unique()
    return list(shortlist)

def apply_filters(filters_applied, course_list):
    if len(filters_applied) == 0:
        return course_list
    gen_ed_df = gen_ed
    ret = []
    for i in filters_applied:
        gen_ed_df = gen_ed_df[gen_ed_df[i]==1]
    valid_courses = list(gen_ed_df["CourseFull"])
    for i in course_list:
        # deal with web scraping BS
        if html.escape(i) in valid_courses:
            ret.append(i)

    return ret

app = Flask(__name__)

COURSE_EXPLORER_BASE = "https://courses.illinois.edu/schedule/DEFAULT/DEFAULT/"

FILTERS = [{'checked': False, 'value': '0', 'text': 'Social & Beh Sci - Soc Sci'},
 {'checked': False, 'value': '1', 'text': 'Cultural Studies - US Minority'},
 {'checked': False, 'value': '2', 'text': 'Humanities - Hist & Phil'},
 {'checked': False, 'value': '3', 'text': 'Humanities - Lit & Arts'},
 {'checked': False, 'value': '4', 'text': 'Cultural Studies - Non-West'},
 {'checked': False, 'value': '5', 'text': 'Advanced Composition'},
 {'checked': False, 'value': '6', 'text': 'Quantitative Reasoning I'},
 {'checked': False, 'value': '7', 'text': 'Nat Sci & Tech - Life Sciences'},
 {'checked': False, 'value': '8', 'text': 'Cultural Studies - Western'},
 {'checked': False, 'value': '9', 'text': 'James Scholars'},
 {'checked': False, 'value': '10', 'text': 'Social & Beh Sci - Beh Sci'},
 {'checked': False, 'value': '11', 'text': 'Camp Honors/Chanc Schol'},
 {'checked': False, 'value': '12', 'text': 'Nat Sci & Tech - Phys Sciences'},
 {'checked': False, 'value': '13', 'text': 'Quantitative Reasoning II'},
 {'checked': False, 'value': '14', 'text': 'Composition I'},
 {'checked': False, 'value': '15', 'text': 'SL CR/SSP'},
 {'checked': False, 'value': '16', 'text': 'Grand Challenge-Sustainability'},
 {'checked': False, 'value': '17', 'text': 'Grand Challenge-Health/Well'},
 {'checked': False, 'value': '18', 'text': 'Grand Challenge-Inequality'},
 {'checked': False, 'value': '19', 'text': 'ONL Info Science rate'},
 {'checked': False, 'value': '20', 'text': 'Ugrad Zero Credit Intern'},
 {'checked': False, 'value': '21', 'text': 'Teacher Certification'},
 {'checked': False, 'value': '22', 'text': 'Offered in Fall 2020'}]

df = pd.read_csv("gpa.csv")
gen_ed = pd.read_csv("gen_ed.csv")

# some preprocessing
WEIGHT = [4.00, 4.00, 3.67, 3.33, 3, 2.67, 2.33, 2, 1.67, 1.33, 1, 0.67, 0]
SEM_FULL_FORM = {'sp': "Spring", 'fa': "Fall", 'su': "Summer", 'wi': "Winter"}
grades = get_grades(df)
semesters = get_semesters(df)

@app.route("/", methods=['GET', 'POST'])
def home():
    semesters = get_semesters(df)
    if len(request.args) != 0:
        imgpath = "/static/images/plot.png"
        filters_applied = []
        for i in request.args:
            if i.isdigit():
                filters_applied.append(i)
        for i in range(len(filters_applied)):
            filters_applied[i] = FILTERS[int(filters_applied[i])]['text']

        prevcourse = request.args["course"]

        course_list = search_course(df, request.args["course"])
        # apply filters
        course_stats = apply_filters(filters_applied, course_list)
        course_stats = df[df['CourseFull'].isin(course_stats)]

        semester = request.args["semester"]
        if semester != "All":
            course_stats = course_stats[course_stats["YearTerm"] == semester]

        uniq_courses = list(course_stats["CourseFull"].unique())

        if "exact" in request.args:
            course_stats = course_stats[course_stats["CourseFull"] == request.args["course"]]
        elif len(uniq_courses) == 0:
            return errmsg("No matching courses found")
        elif len(uniq_courses) != 1: # more than 1 matching course found, generate list
            course_list = []
            for i in list(course_stats["CourseFull"].unique()):
                avg, std = get_avg_gpa(df[df["CourseFull"] == i])
                avg = '%.3f'%avg
                std = '%.3f'%std
                link = "?course="+urllib.parse.quote(i, safe='')+"&semester="+urllib.parse.quote(request.args["semester"], safe='')+"&exact=true"
                course_list.append({'name': i, 'avg': avg, 'std': std, 'link':link})
            course_list = sorted(course_list, key=lambda k: k['avg'], reverse=True)
            return render_template("index.html", semesters=semesters, prevcourse=request.args["course"], course_list=course_list, filters=FILTERS)

        avg_gpa_total, _ = get_avg_gpa(course_stats)
        prof_stats = get_prof_stats(course_stats)
        semester_msg = get_semester_msg(semester)
        pic_hash = gen_plot(course_stats)
        perc = get_perc(course_stats)
        semesters = mark_selected_semesters(semester)

        course_full = course_stats.iloc[0]["CourseFull"]
        subj, num = course_full.split(":")[0].split()
        course_link = COURSE_EXPLORER_BASE + subj + "/" + num

        return render_template("index.html", img=pic_hash + '.png', gpa='%.3f'%avg_gpa_total, perc=perc, prof_stats=prof_stats, semesters=semesters
        , course=course_full, semester=semester_msg, prevcourse=prevcourse, course_explorer=course_link, filters=FILTERS)
    mark_selected_semesters([])
    return render_template("index.html", semesters=semesters, filters=FILTERS)

if __name__ == "__main__":
    app.run(debug=True)
