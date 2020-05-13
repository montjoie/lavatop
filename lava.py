#!/usr/bin/env python3

import curses
from curses import wrapper
import xmlrpc.client
import time
import yaml

JOB_MAX_LINE = 20000

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
cfg["wjobs"] = None

#second colum start
cfg["sc"] = 0

# view job
cfg["wjob"] = None
cfg["vjob"] = None
cfg["vjpad"] = None
cfg["vjob_off"] = 0
# indexed by jobid
wj = {}

try:
    tlabsfile = open("labs.yaml")
except IOError:
    print("ERROR: Cannot open labs config file")
    sys.exit(1)
labs = yaml.safe_load(tlabsfile)

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
        cfg["devices"]["select"] = []
        cfg["workers"]["select"] = None
        return "Switched to %s" % new["name"]
    return "switch error"

switch_lab(True)

def update_workers():
    now = time.time()
    y = -1
    if cfg["wpad"] == None:
        cfg["wpad"] = curses.newpad(100, 100)
    if not "workers" in cache:
        cache["workers"] = {}
        cache["workers"]["detail"] = {}
        cache["workers"]["time"] = 0
    if now - cache["workers"]["time"] > cfg["workers"]["refresh"]:
        cache["workers"]["wlist"] = cfg["lserver"].scheduler.workers.list()
        cache["workers"]["time"] = time.time()
        cache["workers"]["redraw"] = True
    if not cache["workers"]["redraw"]:
        return
    cache["workers"]["redraw"] = False
    cfg["wpad"].clear()
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
    cfg["dpad"].clear()
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
        cfg["devices"]["max"] = di
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
        cfg["jpad"] = curses.newpad(110, 100)
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
    cfg["jpad"].clear()
    jlist = cache["jobs"]["jlist"]
    for job in jlist:
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
        cfg["jpad"].addstr(y, 17, job["submitter"])
        if "actual_device" in job and job["actual_device"] != None:
            if cfg["tab"] == 1 and cfg["sdev"] != None and job["actual_device"] in cfg["sdev"]:
                cfg["jpad"].addstr(y, 29, job["actual_device"], curses.A_BOLD)
            else:
                cfg["jpad"].addstr(y, 29, job["actual_device"])
        y += 1
    cache["jobs"]["redraw"] = False

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
        if cfg["devices"]["offset"] > cfg["devices"]["max"] - cfg["devices"]["display"]:
            cfg["devices"]["offset"] = cfg["devices"]["max"] - cfg["devices"]["display"]
        # check select
        if cfg["select"] > cfg["devices"]["max"]:
            cfg["select"] = cfg["devices"]["max"]
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
        if cfg["select"] > cfg["jobs"]["display"]:
            cfg["select"] = cfg["jobs"]["display"]

# update the vjpad with content of job vjob
def update_job(jobid):
    if jobid == None:
        return
    if not jobid in wj:
        wj[jobid] = {}
        wj[jobid]["wjob"] = curses.newwin(cfg["rows"] - 8, cfg["cols"] - 8, 4, 4)
        wj[jobid]["vjpad"] = curses.newpad(JOB_MAX_LINE, 5000)
        r = cfg["lserver"].scheduler.job_output(jobid)
        logs = yaml.unsafe_load(r.data)
        y = 2
        for line in logs:
            if y > JOB_MAX_LINE:
                y += 1
                continue
            if line['lvl'] == 'info' or line['lvl'] == 'debug' or line['lvl'] == 'target' or line['lvl'] == 'input':
                if line["msg"] == None:
                    continue
                if isinstance(line["msg"], list):
                    wj[jobid]["vjpad"].addstr(y, 0, str(line))
                    y += 1
                    continue
                wj[jobid]["vjpad"].addstr(y, 0, line["msg"].replace('\0', ''))
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
                    wj[jobid]["vjpad"].addstr(y, 0, line["msg"]["error_msg"])
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
        wj[jobid]["wjob"].addstr(1, 1, "JOBID: %s LINES: %d" % (jobid, y))

def main(stdscr):
    # Clear screen
    c = 0
    # worker = 0
    # devices = 1
    msg = ""
    cmd = 0
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    stdscr.timeout(200)


    exit = False
    while not exit:
        now = time.time()
        rows, cols = stdscr.getmaxyx()
        cfg["rows"] = rows
        cfg["cols"] = cols
        if cfg["swin"] == None:
            cfg["swin"] = curses.newwin(3, cfg["cols"], 0, 0)
        cfg["swin"].clear()
        cfg["swin"].addstr(0, 0, "Screen %dx%d Lab: %s Select: %d HELP: UP DOWN TAB [Q]uit" % (cols, rows, cfg["lab"]["name"], cfg["select"]))
        if cfg["tab"] == 0:
            cfg["swin"].addstr(1, 0, "WORKERS HELP: UP DOWN space")
        if cfg["tab"] == 1:
            cfg["swin"].addstr(1, 0, "DEVICES HELP: h+[um] s+[shn] UP DOWN space")
        if cfg["tab"] == 2:
            cfg["swin"].addstr(1, 0, "JOBS HELP: v  PGDN PGUP x")
        cfg["swin"].addstr(2, 0, msg)
        cfg["swin"].refresh()
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
            cfg["wpad"].refresh(0, 0, y, 0, rows - 1, cols - 1)
            y += cfg["workers"]["count"] + 1

        # devices
        if cfg["devices"]["enable"]:
            update_devices()
            if cfg["jobs"]["enable"]:
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
                cfg["devices"]["max"],
                now - cache["device"]["time"],
                cfg["devices"]["refresh"]
                ))
            y += 1
            #verify that select is printable
            check_limits()
            cfg["dpad"].refresh(cfg["devices"]["offset"], 0, y, 0, y_max, cols - 1)
            y += cfg["devices"]["display"] + 1

        if cfg["jobs"]["enable"]:
            update_jobs()
            cfg["jobs"]["display"] = rows - y - 1
            cfg["jpad"].refresh(0, 0, y + 1, 0, rows - 1, cols - 1)
            stdscr.addstr(y, 0, "Jobs 1-%d/?? (refresh %d/%d)" % (cfg["jobs"]["display"], now - cache["jobs"]["time"], cfg["jobs"]["refresh"]))

        if cfg["wjobs"] == None and cfg["sc"] < cfg["cols"] - 30:
            cfg["wjobs"] = curses.newwin(cfg["rows"] - 4, cfg["cols"] - cfg["sc"], 4, cfg["sc"])
        if cfg["wjobs"] != None:
            cfg["wjobs"].box("|", "-")
            cfg["wjobs"].addstr(1, 1, "JOB LIST")
            cfg["wjobs"].refresh()
            cfg["jpad"].refresh(0, 0, 4+1, cfg["sc"] + 1, rows - 2, cols - 2)

        if cfg["vjob"] != None:
            update_job(cfg["vjob"])

        stdscr.refresh()

        if cfg["vjob"] != None:
            wj[cfg["vjob"]]["wjob"].box("|", "-")
            wj[cfg["vjob"]]["wjob"].refresh()
            wj[cfg["vjob"]]["vjpad"].refresh(cfg["vjob_off"], 0, 9, 9, rows - 9, cols - 9)
        #curses.doupdate()
        y += 1
        #msg = ""
        c = stdscr.getch()
        if c == curses.KEY_UP:
            cfg["select"] -= 1
            if cfg["tab"] == 1:
                cache["device"]["redraw"] = True
            elif cfg["tab"] == 0:
                cache["workers"]["redraw"] = True
            else:
                cache["jobs"]["redraw"] = True
        elif c == curses.KEY_DOWN:
            cfg["select"] += 1
            if cfg["tab"] == 1:
                cache["device"]["redraw"] = True
            elif cfg["tab"] == 0:
                cache["workers"]["redraw"] = True
            else:
                cache["jobs"]["redraw"] = True
        elif c == curses.KEY_PPAGE:
            if cfg["tab"] == 1:
                #scroll devices
                cfg["devices"]["offset"] -= 5
                cache["device"]["redraw"] = True
                if cfg["devices"]["offset"] < 0:
                    cfg["devices"]["offset"] = 0
                if cfg["select"] > cfg["devices"]["offset"] + cfg["devices"]["display"]:
                    cfg["select"] = cfg["devices"]["offset"] + cfg["devices"]["display"]
            else:
                # scroll job output
                cfg["vjob_off"] -= 100
        elif c == curses.KEY_NPAGE:
            if cfg["tab"] == 1:
                #scroll devices
                cfg["devices"]["offset"] += 5
                cache["device"]["redraw"] = True
                if cfg["devices"]["offset"] > cfg["devices"]["max"] - 20:
                    cfg["devices"]["offset"] = 0
                if cfg["select"] < cfg["devices"]["offset"]:
                    cfg["select"] = cfg["devices"]["offset"]
            else:
                # scroll job output
                cfg["vjob_off"] += 100
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
        elif c == ord('w'):
            # worker window
            cfg["workers"]["enable"] = not cfg["workers"]["enable"]
            msg = "Windows worker"
        elif c == ord('j'):
            # jobs window
            cfg["jobs"]["enable"] = not cfg["jobs"]["enable"]
            msg = "Windows jobs"
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
            cmd = 0
            cfg["vjob"] = None
            if cfg["vjpad"] != None:
                cfg["vjpad"].clear()
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
        if cfg["tab"] > 2:
            cfg["tab"] = 0
        if cfg["tab"] == 0 and not cfg["workers"]["enable"]:
            cfg["tab"] = 1
        if c == 27 or c == ord('q'):
            exit = True
        check_limits()

wrapper(main)
