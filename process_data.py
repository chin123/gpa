import pandas as pd
import numpy as np
import math


def get_grades(df):
    grades = [i for i in df.columns if len(i) < 3]
    # remove the W
    grades = grades[: len(grades) - 1]
    return grades

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

df = pd.read_csv("uiuc-gpa-dataset.csv")
WEIGHT = [4.00, 4.00, 3.67, 3.33, 3, 2.67, 2.33, 2, 1.67, 1.33, 1, 0.67, 0]
grades = get_grades(df)

cross_mapping = dict()
for i in set(df["Subject"] + " " + df["Number"].astype('str')):
    cross_mapping[i] = i
cross = pd.read_csv("cross.txt", names=['cross', 'orig'])
for ind, row in cross.iterrows():
    if row['orig'] in cross_mapping:
        cross_mapping[row['orig']] += "/" + row['cross']

# generate full course name for regex search
df["CourseFull"] = (df["Subject"] + " " + df["Number"].astype('str')).map(cross_mapping) + ": " + df["Course Title"]

# list of all courses in GPA++
all_courses = set(list(df["Subject"] + " " + df["Number"].astype('str')))

df.to_csv("gpa.csv")

# create overall_gpa for faster searching
overall_gpa = pd.DataFrame(columns=['CourseFull', 'mean', 'std'])
toadd = set(df["CourseFull"])
for course in toadd:
    all_rows = df[df["CourseFull"] == course]
    mean, std = get_avg_gpa(all_rows)
    overall_gpa.loc[len(overall_gpa)] = [course, mean, std]

overall_gpa.to_csv("overall_gpa.csv")

genedreqs = {'ACP':'ACP', 'NW':'CS', 'WCC':'CS', 'US':'CS', 'HP':'HUM', 'LA':'HUM', 'LS':'NAT', 'PS':'NAT', 'QR1':'QR', 'QR2':'QR', 'BSC':'SBS', 'SS':'SBS'}

trans = {'ACP': 'Advanced Composition', 'NW': 'Non-Western Cultures', 'WCC': 'Western/Comparative Cultures', 'US': 'US Minority Cultures', 'HP':'Historical & Philosophical Perspectives', 'LA': 'Literature & the Arts', 'LS': 'Life Sciences', 'PS': 'Physical Sciences', 'QR1': 'Quantitative Reasoning 1', 'QR2': 'Quantitative Reasoning 2', 'BSC': 'Behavioral Sciences', 'SS': 'Social Sciences'}

# read in gen ed dataset
df = pd.read_csv("dataset.csv")

# add all courses which dont satisfy any gen ed req w/ NA for all reqs
row_to_copy = df.iloc[-1]
for j in genedreqs:
    field = genedreqs[j]
    row_to_copy[field] = "NA"

geneds = set(list(df["Course"]))
rem_courses = all_courses - geneds
for i in rem_courses:
    row_to_copy["Course"] = i
    df.loc[len(df)] = row_to_copy

# add 0/1 column for each req in genedreqs
for i in trans:
    newcol = trans[i]
    df[newcol] = 0
    for j,r in df.iterrows():
        if not pd.isnull(df.iloc[j][genedreqs[i]]):
            if df.iloc[j][genedreqs[i]] == i:
                df.loc[j, newcol] = 1

df.to_csv("gen_ed.csv")

