#!/usr/bin/env python3

import curses
from curses import wrapper
import xmlrpc.client
import time
import yaml

cache = {}
cfg = {}
cfg["workers"] = {}
cfg["workers"]["enable"] = True
cfg["workers"]["count"] = 0
cfg["workers"]["redraw"] = False
cfg["workers"]["refresh"] = 60
cfg["workers"]["select"] = []
cfg["devices"] = {}
cfg["devices"]["enable"] = True
cfg["devices"]["count"] = 0
cfg["devices"]["max"] = 0
cfg["devices"]["redraw"] = False
cfg["devices"]["refresh"] = 20
cfg["devices"]["offset"] = 0
# how many device are displayed
cfg["devices"]["display"] = 0
cfg["devices"]["select"] = []
cfg["devices"]["sort"] = 0
cfg["jobs"] = {}
cfg["jobs"]["enable"] = True
cfg["jobs"]["count"] = 0
cfg["jobs"]["redraw"] = False
cfg["jobs"]["refresh"] = 20
# where = 0 on right of screen, 1 is in classic tab
cfg["jobs"]["where"] = 0
cfg["jobs"]["title"] = True
cfg["jobs"]["titletrunc"] = True
cfg["jobs"]["offset"] = 0
cfg["jobs"]["filter"] = []

cfg["tab"] = 0
cfg["select"] = 1
cfg["sjob"] = None
cfg["wpad"] = None
cfg["dpad"] = None
cfg["jpad"] = None
# selected worker
cfg["swk"] = None
# selected device
cfg["sdev"] = None
# current lab
cfg["lab"] = None
# the status window
cfg["swin"] = None
# windows for job list
cfg["wjobs"] = None

# global options
cfg["wopt"] = None
# filter window
cfg["wfilter"] = None

#second colum start
cfg["sc"] = 0

# view job
cfg["wjob"] = None
cfg["vjob"] = None
cfg["vjpad"] = None
cfg["vjob_off"] = 0
# indexed by jobid
wj = {}

cfg["debug"] = None
cfg["debug"] = open("debug.log", 'w')

L_RED = 1
L_GREEN = 2
L_BLUE = 3
L_WHITE = 4
L_CYAN = 5
L_YELLOW = 6
L_TGT = 7
L_INPUT = 8

try:
    tlabsfile = open("labs.yaml")
except IOError:
    print("ERROR: Cannot open labs config file")
    sys.exit(1)
labs = yaml.safe_load(tlabsfile)

def debug(msg):
    if cfg["debug"] == None:
        return
    cfg["debug"].write(msg)
    cfg["debug"].flush()

def switch_lab(usefirst):
    new = None
    usenext = usefirst
    for lab in labs["labs"]:
        if "disabled" in lab and lab["disabled"]:
            continue
        if usenext:
            new = lab
            break
        if cfg["lab"]["name"] == lab["name"]:
            usenext = True
    if new == None:
        # use the first
        for lab in labs["labs"]:
            new = lab
            break

    if new != None:
        if cfg["lab"] != None and cfg["lab"]["name"] == new["name"]:
            return "already this lab"
        #real switch
        cfg["lab"] = new
        LAVAURI = new["lavauri"]
        cfg["lserver"] = xmlrpc.client.ServerProxy(LAVAURI, allow_none=True)
        if "device" in cache:
            cache["device"]["time"] = 0
            for dname in cache["device"]:
                if isinstance(cache["device"][dname], dict):
                    cache["device"][dname]["time"] = 0
        if "workers" in cache:
            cache["workers"]["time"] = 0
            for worker in cache["workers"]["detail"]:
                cache["workers"]["detail"][worker]["time"] = 0
        if "jobs" in cache:
            cache["jobs"]["time"] = 0
        if not "DEVICENAME_LENMAX" in new:
            cfg["lab"]["DEVICENAME_LENMAX"] = 24
        if not "WKNAME_LENMAX" in new:
            cfg["lab"]["WKNAME_LENMAX"] = 10
        if not "JOB_LENMAX" in lab:
            cfg["lab"]["JOB_LENMAX"] = 5
        if not "USER_LENMAX" in lab:
            cfg["lab"]["USER_LENMAX"] = 10
        cfg["devices"]["select"] = []
        cfg["workers"]["select"] = None
        debug("Switched to %s\n" % new["name"])
        return "Switched to %s" % new["name"]
    return "switch error"

switch_lab(True)

def update_workers():
    now = time.time()
    y = -1
    if not "workers" in cache:
        cache["workers"] = {}
        cache["workers"]["detail"] = {}
        cache["workers"]["time"] = 0
    if now - cache["workers"]["time"] > cfg["workers"]["refresh"]:
        cache["workers"]["wlist"] = cfg["lserver"].scheduler.workers.list()
        cache["workers"]["time"] = time.time()
        cache["workers"]["redraw"] = True
    wmax = len(cache["workers"]["wlist"])
    # if the number of worker changed, recreate window
    if "count" in cfg["workers"] and cfg["workers"]["count"] < wmax:
        if cfg["wpad"] != None:
            cfg["wpad"].clear()
            cfg["wpad"].noutrefresh(0, 0, 4, 0, cfg["rows"] - 1, cfg["cols"] - 1)
            cfg["wpad"] = None
    if cfg["wpad"] == None:
        cfg["wpad"] = curses.newpad(wmax + 1, 100)
        cache["workers"]["redraw"] = True
    if not cache["workers"]["redraw"]:
        return
    cache["workers"]["redraw"] = False
    cfg["wpad"].erase()
    wlist = cache["workers"]["wlist"]
    wi = 0
    if cfg["workers"]["select"] == None:
        cfg["workers"]["select"] = []
        for worker in wlist:
            cfg["workers"]["select"].append(worker)
    for worker in wlist:
        if not worker in cache["workers"]["detail"]:
            cache["workers"]["detail"][worker] = {}
            cache["workers"]["detail"][worker]["time"] = 0
        if now - cache["workers"]["detail"][worker]["time"] > 10:
            cache["workers"]["detail"][worker]["time"] = time.time()
            cache["workers"]["detail"][worker]["wdet"] = cfg["lserver"].scheduler.workers.show(worker)
        wdet = cache["workers"]["detail"][worker]["wdet"]
        wi += 1
        cfg["workers"]["count"] = wi
        y += 1
        x = 4
        if worker in cfg["workers"]["select"]:
            cfg["wpad"].addstr(y, 0, "[x]")
        else:
            cfg["wpad"].addstr(y, 0, "[ ]")
        if cfg["select"] == wi and cfg["tab"] == 0:
            cfg["wpad"].addstr(y, x, worker, curses.A_BOLD)
            cfg["swk"] = worker
        else:
            cfg["wpad"].addstr(y, x, worker)
        if len(worker) > cfg["lab"]["WKNAME_LENMAX"]:
            cfg["lab"]["WKNAME_LENMAX"] = len(worker) + 1
            debug("WKNAME_LENMAX set to %d\n" % cfg["lab"]["WKNAME_LENMAX"])
            cache["workers"]["redraw"] = True
        x += cfg["lab"]["WKNAME_LENMAX"]
        if wdet["state"] == 'Offline':
            cfg["wpad"].addstr(y, x, wdet["state"], curses.color_pair(1))
        elif wdet["state"] == 'Online':
            cfg["wpad"].addstr(y, x, wdet["state"], curses.color_pair(2))
        else:
            cfg["wpad"].addstr(y, x, wdet["state"])
        x += 10
        if wdet["health"] == 'Active':
            cfg["wpad"].addstr(y, x, wdet["health"], curses.color_pair(2))
        else:
            cfg["wpad"].addstr(y, x, wdet["health"], curses.color_pair(1))


def update_devices():
    now = time.time()
    y = -1
    if cfg["dpad"] == None:
        cfg["dpad"] = curses.newpad(100, cfg["cols"])
    if not "device" in cache:
        cache["device"] = {}
        cache["device"]["time"] = 0
    if now - cache["device"]["time"] > cfg["devices"]["refresh"]:
        cache["device"]["dlist"] = cfg["lserver"].scheduler.devices.list()
        cache["device"]["time"] = time.time()
        cache["device"]["redraw"] = True
    if not cache["device"]["redraw"]:
        return
    cache["device"]["redraw"] = False
    cfg["dpad"].erase()
    dlist = cache["device"]["dlist"]
    di = 0
    # sort by health
    if cfg["devices"]["sort"] == 1:
        nlist = []
        for device in dlist:
            if device["health"] == 'Bad':
                nlist.append(device)
        for device in dlist:
            if device["health"] == 'Unknown':
                nlist.append(device)
        for device in dlist:
            if device["health"] == 'Good':
                nlist.append(device)
        for device in dlist:
            if device["health"] == 'Maintenance':
                nlist.append(device)
        for device in dlist:
            if device["health"] == 'Retired':
                nlist.append(device)
        dlist = nlist
    if cfg["devices"]["sort"] == 2:
        nlist = []
        for device in dlist:
            if device["state"] == 'Running':
                nlist.append(device)
        for device in dlist:
            if device["state"] == 'Idle':
                nlist.append(device)
        dlist = nlist
    for device in dlist:
        dname = device["hostname"]
        if dname not in cache["device"]:
            cache["device"][dname] = {}
            cache["device"][dname]["time"] = 0
        if now - cache["device"][dname]["time"] > cfg["devices"]["refresh"] * 10:
            cache["device"][dname] = cfg["lserver"].scheduler.devices.show(dname)
            cache["device"][dname]["time"] = time.time()
        ddetail = cache["device"][dname]

        if ddetail["worker"] not in cfg["workers"]["select"]:
            continue
        x = 4
        y += 1
        di += 1
        cfg["devices"]["count"] = di
        if dname in cfg["devices"]["select"]:
            cfg["dpad"].addstr(y, 0, "[x]")
        else:
            cfg["dpad"].addstr(y, 0, "[ ]")
        if cfg["select"] == di and cfg["tab"] == 1:
            cfg["dpad"].addstr(y, x, device["hostname"], curses.A_BOLD)
            cfg["sdev"] = dname
        else:
            cfg["dpad"].addstr(y, x, device["hostname"])
        if len(dname) > cfg["lab"]["DEVICENAME_LENMAX"]:
            cfg["lab"]["DEVICENAME_LENMAX"] = len(dname)
            cache["device"]["redraw"] = True
        x += cfg["lab"]["DEVICENAME_LENMAX"] + 1
        if device["health"] == 'Bad':
            cfg["dpad"].addstr(y, x, device["health"], curses.color_pair(1))
        elif device["health"] == 'Good':
            cfg["dpad"].addstr(y, x, device["health"], curses.color_pair(2))
        elif device["health"] == 'Maintenance':
            cfg["dpad"].addstr(y, x, device["health"], curses.color_pair(3))
        else:
            cfg["dpad"].addstr(y, x, device["health"])
        x += 12
        if device["state"] == 'Running':
            cfg["dpad"].addstr(y, x, device["state"], curses.color_pair(2))
        elif device["state"] == 'Idle':
            cfg["dpad"].addstr(y, x, device["state"], curses.color_pair(3))
        else:
            cfg["dpad"].addstr(y, x, device["state"])
        x += 8
        # TODO add color according to worker state
        wkname = ddetail["worker"]
        if cache["workers"]["detail"][wkname]["wdet"]["state"] == 'Offline':
            cfg["dpad"].addstr(y, x, wkname, curses.color_pair(1))
        elif cfg["tab"] == 0 and cfg["swk"] != None and wkname in cfg["swk"]:
            cfg["dpad"].addstr(y, x, wkname, curses.A_BOLD)
        else:
            cfg["dpad"].addstr(y, x, wkname)
        x += cfg["lab"]["WKNAME_LENMAX"]
        if x > cfg["sc"]:
            cfg["sc"] = x

def update_jobs():
    now = time.time()
    y = 0
    if cfg["jpad"] == None:
        if cfg["jobs"]["where"] == 1:
            w = cfg["cols"] - 2
        else:
            w = cfg["cols"] - cfg["sc"] - 2
        debug("Create jobpad w=%d\n" % w)
        cfg["jpad"] = curses.newpad(210, w)
    ji = 0
    offset = 0
    if "jobs" not in cache:
        cache["jobs"] = {}
        cache["jobs"]["time"] = 0
    if now - cache["jobs"]["time"] > cfg["jobs"]["refresh"]:
        cache["jobs"]["jlist"] = cfg["lserver"].scheduler.jobs.list(None, None, offset, 100, None, True)
        cache["jobs"]["time"] = time.time()
        cache["jobs"]["redraw"] = True
    if not cache["jobs"]["redraw"]:
        return
    cache["jobs"]["redraw"] = False
    cfg["jpad"].erase()
    jlist = cache["jobs"]["jlist"]
    for job in jlist:
        # filter
        if "devselect" in cfg["jobs"]["filter"]:
            if "actual_device" not in job:
                continue
            if job["actual_device"] not in cfg["devices"]["select"]:
                continue
        x = 0
        ji += 1
        cfg["jobs"]["count"] = ji
        jobid = str(job["id"])
        if jobid is int:
            jobid = str(job["id"])
        if cfg["select"] == ji and cfg["tab"] == 2:
            cfg["jpad"].addstr(y, x, jobid, curses.A_BOLD)
            cfg["sjob"] = jobid
        else:
            cfg["jpad"].addstr(y, x, jobid)
        if len(jobid) > cfg["lab"]["JOB_LENMAX"]:
            cfg["lab"]["JOB_LENMAX"] = len(jobid) + 1
        x += cfg["lab"]["JOB_LENMAX"] + 1
        if job["health"] == 'Incomplete':
            cfg["jpad"].addstr(y, x, job["health"], curses.color_pair(1))
        elif job["health"] == 'Complete':
            cfg["jpad"].addstr(y, x, job["health"], curses.color_pair(2))
        elif job["health"] == 'Unknown':
            cfg["jpad"].addstr(y, x, job["health"], curses.color_pair(3))
        else:
            cfg["jpad"].addstr(y, x, job["health"])
        x += 11
        cfg["jpad"].addstr(y, x, job["submitter"])
        if len(job["submitter"]) > cfg["lab"]["USER_LENMAX"]:
            cfg["lab"]["USER_LENMAX"] = len(job["submitter"])
            cache["jobs"]["redraw"] = True
        x += cfg["lab"]["USER_LENMAX"] + 1
        if "actual_device" in job and job["actual_device"] != None:
            if cfg["tab"] == 1 and cfg["sdev"] != None and job["actual_device"] in cfg["sdev"]:
                cfg["jpad"].addstr(y, x, job["actual_device"], curses.A_BOLD)
            else:
                cfg["jpad"].addstr(y, x, job["actual_device"])
        else:
            # print the device type instead
            cfg["jpad"].addstr(y, x, job["device_type"])
        x += cfg["lab"]["DEVICENAME_LENMAX"]
        if cfg["jobs"]["title"]:
            if cfg["jobs"]["titletrunc"]:
                if cfg["jobs"]["where"] == 0:
                    spaces = cfg["cols"] - cfg["sc"] - x
                else:
                    spaces = cfg["cols"] - x
                cfg["jpad"].addstr(y, x, job["description"][:spaces])
                y += 1
            else:
                cfg["jpad"].addstr(y, x, job["description"])
                y += 2
        else:
            y += 1

def check_limits():
    if cfg["select"] < 1:
        cfg["select"] = 1
    # verify limits for worker
    if cfg["tab"] == 0:
        if cfg["select"] > cfg["workers"]["count"]:
            cfg["select"] = cfg["workers"]["count"]
    # verify limits for devices
    if cfg["tab"] == 1:
        # check offset
        if cfg["devices"]["offset"] > cfg["devices"]["count"] - cfg["devices"]["display"]:
            cfg["devices"]["offset"] = cfg["devices"]["count"] - cfg["devices"]["display"]
        # check select
        if cfg["select"] > cfg["devices"]["count"]:
            cfg["select"] = cfg["devices"]["count"]
        if cfg["select"] <= cfg["devices"]["offset"] and cfg["devices"]["offset"] > 0:
            cfg["devices"]["offset"] -= 1
            cache["device"]["redraw"] = True
        if cfg["select"] > cfg["devices"]["offset"] + cfg["devices"]["display"]:
            cfg["devices"]["offset"] += 1
            cache["device"]["redraw"] = True
    # verify limits for jobs
    if cfg["tab"] == 2:
        if cfg["select"] > cfg["jobs"]["count"]:
            cfg["select"] = cfg["jobs"]["count"]
        if cfg["select"] <= cfg["jobs"]["offset"] and cfg["jobs"]["offset"] > 0:
            cfg["jobs"]["offset"] -= 1
            cache["jobs"]["redraw"] = True
        if cfg["select"] > cfg["jobs"]["offset"] + cfg["jobs"]["display"]:
            cfg["jobs"]["offset"] += 1
            cache["jobs"]["redraw"] = True

# update the vjpad with content of job vjob
def update_job(jobid):
    if jobid == None:
        return
    if not jobid in wj:
        wj[jobid] = {}
        debug("Create job window %dx%d for %s\n" % (cfg["rows"] - 8, cfg["cols"] - 8, jobid))
        wj[jobid]["wjob"] = curses.newwin(cfg["rows"] - 8, cfg["cols"] - 8, 4, 4)
        r = cfg["lserver"].scheduler.job_output(jobid)
        logs = yaml.unsafe_load(r.data)
        #fdebug = open("%s.out" % jobid, "w")
        #yaml.dump(logs, fdebug)
        #fdebug.close()
        linecount = 4
        #TODO change 500
        linew = 500
        for line in logs:
            if line['lvl'] == 'info' or line['lvl'] == 'debug' or line['lvl'] == 'target' or line['lvl'] == 'input':
                if isinstance(line["msg"], list):
                    linecount += 1
                    if linew < len(line["msg"]):
                        linew = len(line["msg"])
                elif isinstance(line["msg"], dict):
                    for msg in line["msg"]:
                        if linew < len(line["msg"]):
                            linew = len(msg)
                        linecount += 1
                else:
                    if linew < len(line["msg"]):
                        linew = len(line["msg"])
                    linecount += 1
            elif line['lvl'] == 'results':
                linecount += 1
                if "error_msg" in line["msg"]:
                    for eline in line["msg"]["error_msg"].split("\n"):
                        linecount += 1
                        if linew < len(eline):
                            linew = len(eline)
            else:
                linecount += 1
        debug("Create job pad of %dx%d\n" % (linecount, linew))
        wj[jobid]["linecount"] = linecount
        wj[jobid]["vjpad"] = curses.newpad(linecount, linew)
        y = 2
        for line in logs:
            if y > linecount:
                debug("Linecount overflow %d" % y)
            color = 4
            if line['lvl'] == 'info':
                color = L_CYAN
            if line['lvl'] == 'debug':
                color = L_WHITE
            if line['lvl'] == 'error':
                color = L_RED
            if line['lvl'] == 'target':
                color = L_TGT
            if line['lvl'] == 'input':
                color = L_INPUT
            if line['lvl'] == 'info' or line['lvl'] == 'debug' or line['lvl'] == 'target' or line['lvl'] == 'input':
                if line["msg"] == None:
                    continue
                if isinstance(line["msg"], list):
                    wj[jobid]["vjpad"].addstr(y, 0, str(line))
                    y += 1
                    continue
                wj[jobid]["vjpad"].addstr(y, 0, line["msg"].replace('\0', ''), curses.color_pair(color))
                y += 1
                continue
            if line['lvl'] == 'error':
                wj[jobid]["vjpad"].addstr(y, 0, line["msg"], curses.color_pair(1))
                y += 1
                continue
            if line['lvl'] == 'results':
                wj[jobid]["vjpad"].addstr(y, 0, "TEST: %s %s %s" % (line["msg"]["case"], line["msg"]["definition"], line["msg"]["result"]))
                y += 1
                if "error_msg" in line["msg"]:
                    wj[jobid]["vjpad"].addstr(y, 0, line["msg"]["error_msg"], curses.color_pair(1))
                    y += 1
                continue
            if isinstance(line["msg"], dict):
                for msg in line["msg"]:
                    wj[jobid]["vjpad"].addstr(y, 0, msg)
                    y += 1
            elif isinstance(line["msg"], list):
                wj[jobid]["vjpad"].addstr(y, 0, str(line))
                y += 1
            else:
                wj[jobid]["vjpad"].addstr(y, 0, line["msg"].rstrip('\0'))
                y += 1

def global_options():
    cfg["wopt"].box("|", "-")
    if cfg["workers"]["enable"]:
        cfg["wopt"].addstr(2, 2, "[x] show [w]orkers tab")
    else:
        cfg["wopt"].addstr(2, 2, "[ ] show [w]orkers tab")
    if cfg["devices"]["enable"]:
        cfg["wopt"].addstr(3, 2, "[x] show [d]evices tab")
    else:
        cfg["wopt"].addstr(3, 2, "[ ] show [d]evices tab")
    if cfg["jobs"]["enable"]:
        cfg["wopt"].addstr(4, 2, "[x] show jobs tab")
    else:
        cfg["wopt"].addstr(4, 2, "[ ] show jobs tab")
    if cfg["jobs"]["where"] == 1:
        cfg["wopt"].addstr(5, 2, "[ ] display jobs on the right")
    else:
        cfg["wopt"].addstr(5, 2, "[x] display jobs on the right")
    if cfg["jobs"]["title"]:
        cfg["wopt"].addstr(6, 2, "[x] display job [t]itle")
    else:
        cfg["wopt"].addstr(6, 2, "[ ] display job [t]itle")
    if cfg["jobs"]["titletrunc"]:
        cfg["wopt"].addstr(7, 2, "[x] [T]runcate job title")
    else:
        cfg["wopt"].addstr(7, 2, "[ ] [T]runcate job title")
    cfg["wopt"].addstr(2, 30, "DEVICENAME_LENMAX: %d" % cfg["lab"]["DEVICENAME_LENMAX"])

def display_filters():
    cfg["wfilter"].box("|", "-")
    cfg["wfilter"].addstr(2, 2, "Devices filter")
    if "devselect" in cfg["jobs"]["filter"]:
        cfg["wfilter"].addstr(3, 2, "1 [x] Filter jobs from selected devices")
    else:
        cfg["wfilter"].addstr(3, 2, "1 [ ] Filter jobs from selected devices")
    cfg["wfilter"].addstr(20, 2, "Jobs filter")

def main(stdscr):
    # Clear screen
    c = 0
    # worker = 0
    # devices = 1
    msg = ""
    cmd = 0
    curses.init_pair(L_RED, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(L_GREEN, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(L_BLUE, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(L_WHITE, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(L_CYAN, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(L_YELLOW, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(L_TGT, curses.COLOR_GREEN, curses.COLOR_WHITE)
    curses.init_pair(L_INPUT, curses.COLOR_BLACK, curses.COLOR_WHITE)
    stdscr.timeout(500)


    exit = False
    while not exit:
        now = time.time()
        rows, cols = stdscr.getmaxyx()
        cfg["rows"] = rows
        cfg["cols"] = cols
        if cfg["swin"] == None:
            cfg["swin"] = curses.newwin(3, cfg["cols"], 0, 0)
        cfg["swin"].erase()
        cfg["swin"].addstr(0, 0, "Screen %dx%d Lab: %s Select: %d HELP: UP DOWN TAB [Q]uit [f]ilters [o]ptions" % (cols, rows, cfg["lab"]["name"], cfg["select"]))
        if cfg["tab"] == 0:
            cfg["swin"].addstr(1, 0, "WORKERS HELP: UP DOWN space")
        if cfg["tab"] == 1:
            cfg["swin"].addstr(1, 0, "DEVICES HELP: h+[um] s+[shn] UP DOWN space")
        if cfg["tab"] == 2:
            cfg["swin"].addstr(1, 0, "JOBS HELP: v  PGDN PGUP x")
        cfg["swin"].addstr(2, 0, msg)
        cfg["swin"].noutrefresh()
        if cfg["tab"] != 2:
            cfg["sjob"] = None

        y = 3
        if cfg["workers"]["enable"]:
            update_workers()
            check_limits()
            
            stdscr.addstr(y, 0, "Workers %d-%d/%d (refresh %d/%d)" %
                (
                1,
                cfg["workers"]["count"],
                cfg["workers"]["count"],
                now - cache["workers"]["time"],
                cfg["workers"]["refresh"]
                ))
            y += 1
            cfg["wpad"].noutrefresh(0, 0, y, 0, rows - 1, cols - 1)
            y += cfg["workers"]["count"] + 1

        # devices
        if cfg["devices"]["enable"]:
            update_devices()
            if cfg["jobs"]["enable"] and cfg["jobs"]["where"] == 1:
                y_max = rows - 15
            else:
                y_max = rows - 1
            cfg["devices"]["display"] = y_max - y
            if cfg["devices"]["display"] > cfg["devices"]["count"]:
                cfg["devices"]["display"] = cfg["devices"]["count"]
            stdscr.addstr(y, 0, "Devices %d-%d/%d (refresh %d/%d)" %
                (
                cfg["devices"]["offset"] + 1,
                cfg["devices"]["display"] + cfg["devices"]["offset"],
                cfg["devices"]["count"],
                now - cache["device"]["time"],
                cfg["devices"]["refresh"]
                ))
            y += 1
            #verify that select is printable
            check_limits()
            cfg["dpad"].noutrefresh(cfg["devices"]["offset"], 0, y, 0, y_max, cols - 1)
            y += cfg["devices"]["display"] + 1

        if cfg["sc"] > cfg["cols"] - 65 and cfg["jobs"]["where"] == 0:
            # too small, cannot print jobs on right
            cfg["jobs"]["where"] = 1
            msg = "TOO SMALL %d %d %d" % (cfg["sc"], cfg["cols"], cfg["cols"] - 30)
            debug("Downgrade to no job windows sc=%d cols=%d\n" % (cfg["sc"], cfg["cols"]))
        if cfg["jobs"]["enable"]:
            update_jobs()
            if cfg["jobs"]["where"] == 1:
                # on first switch we cannot display jobs
                if rows > y:
                    cfg["jobs"]["display"] = rows - y - 1
                    if cfg["jobs"]["title"] and not cfg["jobs"]["titletrunc"]:
                        cfg["jobs"]["display"] = cfg["jobs"]["display"] / 2
                    #debug("display=%d y=%d row=%d cols=%d offset=%d" % (cfg["jobs"]["display"], y, rows, cols, cfg["jobs"]["offset"]))
                    cfg["jpad"].noutrefresh(cfg["jobs"]["offset"], 0, y + 1, 0, rows - 1, cols - 1)
                    stdscr.addstr(y, 0, "Jobs %d-%d/%d (refresh %d/%d)" % (
                    cfg["jobs"]["offset"] + 1,
                    cfg["jobs"]["display"] + cfg["jobs"]["offset"],
                    cfg["jobs"]["count"],
                    now - cache["jobs"]["time"],
                    cfg["jobs"]["refresh"]))
            else:
                cfg["jobs"]["display"] = cfg["rows"] - 7
                if cfg["jobs"]["title"] and not cfg["jobs"]["titletrunc"]:
                    cfg["jobs"]["display"] = cfg["jobs"]["display"] / 2

        if cfg["wjobs"] == None and cfg["jobs"]["where"] == 0:
            cfg["wjobs"] = curses.newwin(cfg["rows"] - 4, cfg["cols"] - cfg["sc"], 4, cfg["sc"])
        if cfg["wjobs"] != None:
            cfg["wjobs"].box("|", "-")
            cfg["wjobs"].addstr(1, 1, "Jobs %d-%d/%d (refresh %d/%d)" % (
                cfg["jobs"]["offset"] + 1,
                cfg["jobs"]["display"] + cfg["jobs"]["offset"],
                cfg["jobs"]["count"],
                now - cache["jobs"]["time"],
                cfg["jobs"]["refresh"]))
            cfg["wjobs"].noutrefresh()
            cfg["jpad"].noutrefresh(cfg["jobs"]["offset"], 0, 4+2, cfg["sc"] + 1, rows - 2, cols - 2)

        if cfg["vjob"] != None:
            update_job(cfg["vjob"])

        stdscr.noutrefresh()

        if cfg["vjob"] != None:
            wj[cfg["vjob"]]["wjob"].addstr(1, 1, "JOBID: %s LINES: %d-x/%d" % (cfg["vjob"], cfg["vjob_off"], wj[cfg["vjob"]]["linecount"]))
            wj[cfg["vjob"]]["wjob"].box("|", "-")
            wj[cfg["vjob"]]["wjob"].noutrefresh()
            wj[cfg["vjob"]]["vjpad"].noutrefresh(cfg["vjob_off"], 0, 9, 9, rows - 9, cols - 9)

        if cfg["wfilter"] != None:
            display_filters()
            cfg["wfilter"].noutrefresh()

        if cfg["wopt"] != None:
            global_options()
            cfg["wopt"].noutrefresh()

        curses.doupdate()

        #curses.doupdate()
        y += 1
        #msg = ""
        c = stdscr.getch()
        if c == curses.KEY_UP:
            if cfg["vjob"] != None:
                # scroll job output
                cfg["vjob_off"] -= 1
            else:
                cfg["select"] -= 1
                if cfg["tab"] == 1:
                    cache["device"]["redraw"] = True
                elif cfg["tab"] == 0:
                    cache["workers"]["redraw"] = True
                else:
                    cache["jobs"]["redraw"] = True
        elif c == curses.KEY_DOWN:
            if cfg["vjob"] != None:
                # scroll job output
                cfg["vjob_off"] += 1
            else:
                cfg["select"] += 1
                if cfg["tab"] == 1:
                    cache["device"]["redraw"] = True
                elif cfg["tab"] == 0:
                    cache["workers"]["redraw"] = True
                else:
                    cache["jobs"]["redraw"] = True
        elif c == curses.KEY_PPAGE:
            if cfg["vjob"] != None:
                # scroll job output
                cfg["vjob_off"] -= 20
            elif cfg["tab"] == 1:
                #scroll devices
                cfg["devices"]["offset"] -= 5
                cache["device"]["redraw"] = True
                if cfg["devices"]["offset"] < 0:
                    cfg["devices"]["offset"] = 0
                # the select could has been hidden
                if cfg["select"] > cfg["devices"]["offset"] + cfg["devices"]["display"]:
                    cfg["select"] = cfg["devices"]["offset"] + cfg["devices"]["display"]
            elif cfg["tab"] == 2:
                cfg["jobs"]["offset"] -= 5
                cache["jobs"]["redraw"] = True
                if cfg["jobs"]["offset"] < 0:
                    cfg["jobs"]["offset"] = 0
                # the select could has been hidden
                if cfg["select"] > cfg["jobs"]["offset"] + cfg["jobs"]["display"]:
                    cfg["select"] = cfg["jobs"]["offset"] + cfg["jobs"]["display"]
        elif c == curses.KEY_NPAGE:
            if cfg["vjob"] != None:
                # scroll job output
                cfg["vjob_off"] += 20
            elif cfg["tab"] == 1:
                #scroll devices
                cfg["devices"]["offset"] += 5
                cache["device"]["redraw"] = True
                if cfg["devices"]["offset"] > cfg["devices"]["count"] - cfg["devices"]["display"]:
                    cfg["devices"]["offset"] = cfg["devices"]["count"] - cfg["devices"]["display"]
                # the select could has been hidden
                if cfg["select"] < cfg["devices"]["offset"]:
                    cfg["select"] = cfg["devices"]["offset"]
            elif cfg["tab"] == 2:
                #scroll jobs
                cfg["jobs"]["offset"] += 5
                cache["jobs"]["redraw"] = True
                if cfg["jobs"]["offset"] > cfg["jobs"]["count"] - cfg["jobs"]["display"]:
                    cfg["jobs"]["offset"] = cfg["jobs"]["count"] - cfg["jobs"]["display"]
                # the select could has been hidden
                if cfg["select"] < cfg["jobs"]["offset"]:
                    cfg["select"] = cfg["jobs"]["offset"]
        elif c == ord("="):
            if cfg["tab"] == 0:
                cfg["workers"]["select"] = []
                cfg["workers"]["select"].append(cfg["swk"])
                cache["device"]["redraw"] = True
                cache["workers"]["redraw"] = True
        elif c == ord(" "):
            if cfg["tab"] == 0:
                if cfg["swk"] in cfg["workers"]["select"]:
                    cfg["workers"]["select"].remove(cfg["swk"])
                else:
                    cfg["workers"]["select"].append(cfg["swk"])
                cache["device"]["redraw"] = True
                cache["workers"]["redraw"] = True
            if cfg["tab"] == 1:
                if cfg["sdev"] in cfg["devices"]["select"]:
                    cfg["devices"]["select"].remove(cfg["sdev"])
                else:
                    cfg["devices"]["select"].append(cfg["sdev"])
                cache["device"]["redraw"] = True
                if "devselect" in cfg["jobs"]["filter"]:
                    cache["jobs"]["redraw"] = True
        elif c == 9:
            # TAB
            if cfg["tab"] == 0:
                cfg["tab"] = 1
                cache["workers"]["redraw"] = True
                cache["device"]["redraw"] = True
                msg = "Switched to devices tab"
            elif cfg["tab"] == 1:
                cfg["tab"] = 2
                cache["device"]["redraw"] = True
                cache["jobs"]["redraw"] = True
                msg = "Switched to jobs tab"
            else:
                cfg["tab"] = 0
                cache["jobs"]["redraw"] = True
                cache["workers"]["redraw"] = True
                msg = "Switched to worker tab"
        elif cmd > 0 and c > 0:
            # want a subcommand
            if cmd == ord('h'):
                if c == ord('u'):
                    msg = "Set %s to unknow" % cfg["sdev"]
                    cfg["lserver"].scheduler.devices.update(cfg["sdev"], None, None, None, None, 'UNKNOWN')
                    cache["device"]["time"] = 0
                    cmd = 0
                elif c == ord('m'):
                    msg = "Set %s to maintenance" % cfg["sdev"]
                    cfg["lserver"].scheduler.devices.update(cfg["sdev"], None, None, None, None, 'MAINTENANCE')
                    cache["device"]["time"] = 0
                    cmd = 0
                elif c > 0:
                    cmd = 0
                    msg = "Invalid health %s" % curses.unctrl(c)
            elif cmd == ord('l'):
                if c == ord('n'):
                    cmd = 0
                    msg = switch_lab(False)
                    stdscr.erase()
            elif cmd == ord('s'):
                if c == ord('n'):
                    msg = "Sort by name"
                    cfg["devices"]["sort"] = 0
                    cache["device"]["redraw"] = True
                elif c == ord('h'):
                    msg = "Sort by health"
                    cfg["devices"]["sort"] = 1
                    cache["device"]["redraw"] = True
                elif c == ord('s'):
                    msg = "Sort by state"
                    cfg["devices"]["sort"] = 2
                    cache["device"]["redraw"] = True
                else:
                    cmd = 0
                    msg = "Invalid sort"
            else:
                cmd = 0
                msg = "Invalid subcomand %s" % curses.unctrl(c)
        elif c == ord('f'):
            if cfg["wfilter"] == None:
                cfg["wfilter"] = curses.newwin(cfg["rows"] - 8, cfg["cols"] - 8, 4, 4)
            else:
                cfg["wfilter"] = None
        elif c == ord('1'):
            if cfg["wfilter"] != None:
                if "devselect" in cfg["jobs"]["filter"]:
                    cfg["jobs"]["filter"].remove("devselect")
                else:
                    cfg["jobs"]["filter"].append("devselect")
        elif c == ord('w'):
            # worker window
            cfg["workers"]["enable"] = not cfg["workers"]["enable"]
            if not cfg["workers"]["enable"] and cfg["tab"] == 0:
                cfg["tab"] = 1
            msg = "Windows worker"
        elif c == ord('j'):
            # jobs window
            cfg["jobs"]["enable"] = not cfg["jobs"]["enable"]
            msg = "Windows jobs"
        elif c == ord('O') or c == ord('o'):
            if cfg["wopt"] == None:
                cfg["wopt"] = curses.newwin(cfg["rows"] - 8, cfg["cols"] - 8, 4, 4)
            else:
                cfg["wopt"] = None
        elif c == ord('l'):
            # lab switch
            cmd = c
            msg = "lab switch: Next or lab number"
        elif c == ord('h'):
            if cfg["tab"] == 1:
                cmd = c
                msg = "Set health of %s to " % cfg["sdev"]
            else:
                msg = "Invalid"
                cmd = 0
        elif c == ord('x'):
            # close
            if cfg["wopt"] != None:
                cfg["wopt"] = None
            else:
                cmd = 0
                cfg["vjob"] = None
                if cfg["vjpad"] != None:
                    cfg["vjpad"].erase()
        elif c == ord('r'):
            if cfg["tab"] == 0:
                cache["workers"]["time"] = 0
            elif cfg["tab"] == 1:
                cache["device"]["time"] = 0
            else:
                cache["jobs"]["time"] = 0
        elif c == ord('R'):
            #refresh all
            cache["workers"]["time"] = 0
            cache["device"]["time"] = 0
            cache["jobs"]["time"] = 0
            msg = "Refresh all"
        elif c == ord('t'):
            cfg["jobs"]["title"] = not cfg["jobs"]["title"]
            cfg["jobs"]["refresh"] = True
        elif c == ord('T'):
            cfg["jobs"]["titletrunc"] = not cfg["jobs"]["titletrunc"]
            cfg["jobs"]["refresh"] = True
        elif c == ord('s'):
            cmd = c
            msg = "Sort by ? (h n s)"
        elif c == ord('v'):
            if cfg["tab"] == 2:
                msg = "View job %s" % cfg["sjob"]
                cfg["vjob"] = cfg["sjob"]
            else:
                msg = "Invalid"
        if cfg["vjob_off"] < 0:
            cfg["vjob_off"] = 0
            msg = "STOP"
        if cfg["vjob"] != None and cfg["vjob"] in wj and cfg["vjob_off"] > wj[cfg["vjob"]]["linecount"] - 1:
            cfg["vjob_off"] = wj[cfg["vjob"]]["linecount"] - 1
        if cfg["tab"] > 2:
            cfg["tab"] = 0
        if cfg["tab"] == 0 and not cfg["workers"]["enable"]:
            cfg["tab"] = 1
        if c == 27 or c == ord('q'):
            if cfg["wopt"] != None:
                cfg["wopt"] = None
            else:
                exit = True
        check_limits()
    # this is exit
    if cfg["debug"] != None:
        cfg["debug"].close()

wrapper(main)
