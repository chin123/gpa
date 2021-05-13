import base64
import csv
import hashlib
import html
import io
import math
import re2
import urllib
import matplotlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS, cross_origin


def get_filters_satisfied(satisfy_info):
    filters_satisfied = ""
    for k in FILTERS:
        filter_name = k["text"]
        if satisfy_info.iloc[0][filter_name] == 1:
            filters_satisfied += filter_name + ", "
    filters_satisfied = filters_satisfied[:-2]
    return filters_satisfied


def errmsg(msg, ret_json):
    if ret_json:
        return jsonify({"err": msg})
    return render_template(
        "index.html",
        err=msg,
        semesters=semesters,
        prevcourse=request.args["course"],
        filters=FILTERS,
    )


def get_grades(df):
    grades = [i for i in df.columns if len(i) < 3]
    # remove the W
    grades = grades[: len(grades) - 1]
    return grades


def get_semesters(df):
    semesters = []
    for i in df["YearTerm"].unique():
        fullname = SEM_FULL_FORM[i.split("-")[1]] + " " + i.split("-")[0]
        semesters.append({"value": i, "text": fullname, "selected": False})

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
    gpasum = 0
    stdsum = 0
    numstudents = course_stats[grades].sum().sum()
    for i in course_stats[grades].sum():
        gpasum += i * WEIGHT[ind]
        ind += 1
    mean = gpasum / numstudents
    ind = 0
    for i in course_stats[grades].sum():
        stdsum += ((WEIGHT[ind] - mean) ** 2) * i
        ind += 1
    stdsum /= numstudents
    std = math.sqrt(stdsum)
    return mean, std


def get_prof_stats(course_stats):
    # Calculate avg gpa per instructor
    grade_prof_col = grades + ["Primary Instructor"]
    prof_stats_df = (
        course_stats[grade_prof_col].groupby("Primary Instructor").sum()
    )
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
        max_num_students = max(list(row[grades]))
        plot, _ = gen_plot(row[grades], {"kind": "pie", "figsize": (3,3), "radius":1.3})
        prof_stats.append(
            {
                "prof": row.name,
                "total": int(num_students),
                "avg": "%.3f" % float(avg_gpa),
                "std": "%.3f" % float(std_gpa),
                "plot": plot + ".png",
            }
        )
    prof_stats = sorted(prof_stats, key=lambda k: k["avg"], reverse=True)
    return prof_stats


def gen_plot(course_stats, plot_type):
    # Create grade distribution plot
    ax=course_stats.plot(**plot_type)
    ax.set_ylabel('')

    pic_IObytes = io.BytesIO()
    centre_circle = plt.Circle((0,0), 0.9,fc='white')
    fig = plt.gcf()
    if plot_type["kind"] == "pie":
      fig.gca().add_artist(centre_circle)
    plt.savefig(pic_IObytes, format="png")
    pic_IObytes.seek(0)
    base64_img = base64.b64encode(pic_IObytes.read())
    pic_IObytes.seek(0)

    BLOCKSIZE = 65536
    hasher = hashlib.sha1()
    buf = pic_IObytes.read(BLOCKSIZE)
    while len(buf) > 0:
        hasher.update(buf)
        buf = pic_IObytes.read(BLOCKSIZE)
    pic_hash = hasher.hexdigest()
    fname = "static/images/" + pic_hash + ".png"

    plt.savefig(fname)
    plt.clf()
    return pic_hash, base64_img


def get_perc(course_stats):
    # Calculate % of students in each grade
    perc = []
    num_students_total = course_stats[grades].sum().sum()
    for (g, n) in zip(grades, course_stats[grades].sum()):
        perc.append({"g": g, "p": "%.3f" % ((n / num_students_total) * 100)})
    return perc


def get_semester_msg(semester):
    if semester == "All":
        semester_msg = "All Semesters"
    else:
        semester_msg = (
            SEM_FULL_FORM[semester.split("-")[1]] + " " + semester.split("-")[0]
        )
    return semester_msg


def mark_selected_semesters(semester):
    for i in range(len(semesters)):
        semesters[i]["selected"] = False
        if semesters[i]["value"] == semester:
            semesters[i]["selected"] = True

    return semesters


def search_course(df, regex):
    regex = "(?i)" + regex.upper()
    all_courses = list(df["CourseFull"].unique())
    try:
        r = re2.compile(regex)
    except re2.error:
        return [], False
    shortlist = list(filter(r.match, all_courses))
    print(shortlist)
    return shortlist, True


def apply_filters(filters_applied, course_list):
    print("------start")
    gen_ed_df = gen_ed
    ret = []
    for i in filters_applied:
        gen_ed_df = gen_ed_df[gen_ed_df[i] == 1]
    valid_courses = list(gen_ed_df["Course"])
    print("-------------")
    course_df = df[(df["CourseFull"]).isin(course_list)]
    course_df = course_df[(course_df["Subject"] + " " + course_df["Number"].astype('str')).isin(valid_courses)]

    print("------end")
    return list(course_df["CourseFull"].unique())


def get_filters_applied(request):
    if len(request.args) != 0:
        filters_applied = [i for i in request.args if i.isdigit()]
        for i in range(len(filters_applied)):
            FILTERS[int(filters_applied[i])]["checked"] = True
            filters_applied[i] = FILTERS[int(filters_applied[i])]["text"]
    return filters_applied


def gen_course_list(course_stats):
    course_list = []
    cur_courses = course_stats["CourseFull"].unique()
    gpa_data = overall_gpa[overall_gpa["CourseFull"].isin(cur_courses)]
    for i,r in gpa_data.iterrows():
        avg = gpa_data.loc[i]["mean"]
        std = gpa_data.loc[i]["std"]
        name = gpa_data.loc[i]["CourseFull"]
        avg = "%.3f" % float(avg)
        std = "%.3f" % float(std)
        link = (
            "?course="
            + urllib.parse.quote(name, safe="")
            + "&semester="
            + urllib.parse.quote(request.args["semester"], safe="")
            + "&exact=true"
        )
        print("link: " + link)
        course_list.append({"name": name, "avg": avg, "std": std, "link": link})
    course_list = sorted(course_list, key=lambda k: k["avg"], reverse=True)
    return course_list


app = Flask(__name__)
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

matplotlib.use('Agg')

COURSE_EXPLORER_BASE = "https://courses.illinois.edu/schedule/DEFAULT/DEFAULT/"
overall_gpa = dict()

filter_categories = {'ACP': 'Advanced Composition', 'NW': 'Non-Western Cultures', 'WCC': 'Western/Comparative Cultures', 'US': 'US Minority Cultures', 'HP':'Historical & Philosophical Perspectives', 'LA': 'Literature & the Arts', 'LS': 'Life Sciences', 'PS': 'Physical Sciences', 'QR1': 'Quantitative Reasoning 1', 'QR2': 'Quantitative Reasoning 2', 'BS': 'Behavioral Sciences', 'SS': 'Social Sciences'}

FILTERS = []
temp_counter = 0
for i in filter_categories:
    FILTERS.append({"checked": False, "value": str(temp_counter), "text": filter_categories[i]})
    temp_counter += 1

df = pd.read_csv("gpa.csv")
gen_ed = pd.read_csv("gen_ed.csv")
overall_gpa = pd.read_csv("overall_gpa.csv")

# some preprocessing
WEIGHT = [4.00, 4.00, 3.67, 3.33, 3, 2.67, 2.33, 2, 1.67, 1.33, 1, 0.67, 0]
SEM_FULL_FORM = {"sp": "Spring", "fa": "Fall", "su": "Summer", "wi": "Winter"}
grades = get_grades(df)
semesters = get_semesters(df)

@app.route("/", methods=["GET", "POST"])
@cross_origin()
def home():
    semesters = get_semesters(df)

    if "json" in request.args:
        ret_json = True
    else:
        ret_json = False

    if len(request.args) == 0:
        mark_selected_semesters([])
        return render_template(
            "index.html", semesters=semesters, filters=FILTERS
        )

    for i in range(len(FILTERS)):
        FILTERS[i]["checked"] = False

    prevcourse = urllib.parse.unquote(request.args["course"])
    print("prevcourse: " + prevcourse + "end")

    course_list, success = search_course(df, prevcourse)
    if not success:
        return errmsg("Invalid regular expression", ret_json)
    # apply filters
    filters_applied = get_filters_applied(request)
    course_stats = apply_filters(filters_applied, course_list)
    course_stats = df[df["CourseFull"].isin(course_stats)]

    semester = request.args["semester"]
    if semester != "All":
        course_stats = course_stats[course_stats["YearTerm"] == semester]

    uniq_courses = list(course_stats["CourseFull"].unique())

    if "exact" in request.args:
        course_stats = df[
            df["CourseFull"] == prevcourse
        ]
    elif len(uniq_courses) == 0:
        return errmsg("No matching courses found", ret_json)
    elif (
        len(uniq_courses) != 1
    ):  # more than 1 matching course found, generate list
        course_list = gen_course_list(course_stats)
        if ret_json:
            return jsonify({"course_list": course_list})
        return render_template(
            "index.html",
            semesters=semesters,
            prevcourse=request.args["course"],
            course_list=course_list,
            filters=FILTERS,
        )

    avg_gpa_total, _ = get_avg_gpa(course_stats)
    prof_stats = get_prof_stats(course_stats)
    semester_msg = get_semester_msg(semester)
    pic_hash, base64_img = gen_plot(course_stats[grades].sum(), {"kind": "bar", "figsize": (7,5)})
    perc = get_perc(course_stats)
    semesters = mark_selected_semesters(semester)

    course_full = course_stats.iloc[0]["CourseFull"]
    subj, num = course_full.split(":")[0].split()
    satisfy_info = gen_ed[gen_ed["Course"] == (subj + " " + num)]
    course_link = COURSE_EXPLORER_BASE + subj + "/" + num

    filters_satisfied = get_filters_satisfied(satisfy_info)

    if ret_json:
        return jsonify(
            {
                "gpa": "%.3f" % avg_gpa_total,
                "perc": perc,
                "course": course_full,
                "course_explorer": course_link,
                "satisfies": filters_satisfied,
                "img": base64_img.decode("utf-8"),
                "prof_stats": prof_stats,
            }
        )

    return render_template(
        "index.html",
        img=pic_hash + ".png",
        gpa="%.3f" % avg_gpa_total,
        perc=perc,
        prof_stats=prof_stats,
        semesters=semesters,
        course=course_full,
        semester=semester_msg,
        prevcourse=prevcourse,
        course_explorer=course_link,
        filters=FILTERS,
        satisfies=filters_satisfied,
    )


if __name__ == "__main__":
    app.run(debug=True)
