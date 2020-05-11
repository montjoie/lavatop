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
cfg["devices"] = {}
cfg["devices"]["enable"] = True
cfg["devices"]["count"] = 0
cfg["devices"]["max"] = 0
cfg["devices"]["redraw"] = False
cfg["devices"]["refresh"] = 20
cfg["devices"]["offset"] = 0
# how many device are displayed
cfg["devices"]["display"] = 0
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
cfg["sdev"] = None
cfg["lab"] = None

try:
    tlabsfile = open("labs.yaml")
except IOError:
    print("ERROR: Cannot open labs config file")
    sys.exit(1)
labs = yaml.safe_load(tlabsfile)
for lab in labs["labs"]:
    if "disabled" in lab and lab["disabled"]:
        continue
    cfg["lab"] = lab["name"]
    break
LAVAURI = lab["lavauri"]
cfg["lserver"] = xmlrpc.client.ServerProxy(LAVAURI, allow_none=True)

def switch_lab():
    new = None
    usenext = False
    for lab in labs["labs"]:
        if "disabled" in lab and lab["disabled"]:
            continue
        if usenext:
            new = lab
            break
        if cfg["lab"] == lab["name"]:
            usenext = True
    if new == None:
        # use the first
        for lab in labs["labs"]:
            new = lab
            break

    if new != None:
        if cfg["lab"] == new["name"]:
            return "already this lab"
        #real switch
        cfg["lab"] = new["name"]
        LAVAURI = new["lavauri"]
        cfg["lserver"] = xmlrpc.client.ServerProxy(LAVAURI, allow_none=True)
        cache["device"]["time"] = 0
        cache["workers"]["time"] = 0
        cache["jobs"]["time"] = 0
        return "Switched to %s" % new["name"]
    return "switch error"

def update_workers():
    now = time.time()
    y = -1
    if cfg["wpad"] == None:
        cfg["wpad"] = curses.newpad(100, 100)
    if not "workers" in cache:
        cache["workers"] = {}
        cache["workers"]["time"] = 0
    if now - cache["workers"]["time"] > cfg["workers"]["refresh"]:
        cache["workers"]["wlist"] = cfg["lserver"].scheduler.workers.list()
        cache["workers"]["time"] = time.time()
        cache["workers"]["redraw"] = True
    if not cache["workers"]["redraw"]:
        return
    cfg["wpad"].clear()
    wlist = cache["workers"]["wlist"]
    wi = 0
    for worker in wlist:
        wdet = cfg["lserver"].scheduler.workers.show(worker)
        wi += 1
        cfg["workers"]["count"] = wi
        y += 1
        if cfg["select"] == wi and cfg["tab"] == 0:
            cfg["wpad"].addstr(y, 0, worker, curses.A_BOLD)
        else:
            cfg["wpad"].addstr(y, 0, worker)
        if wdet["state"] == 'Offline':
            cfg["wpad"].addstr(y, 20, wdet["state"], curses.color_pair(1))
        else:
            cfg["wpad"].addstr(y, 20, wdet["state"])
        cfg["wpad"].addstr(y, 30, wdet["health"])
    cache["workers"]["redraw"] = False

def update_devices():
    now = time.time()
    y = -1
    if cfg["dpad"] == None:
        cfg["dpad"] = curses.newpad(100, 100)
    if not "device" in cache:
        cache["device"] = {}
        cache["device"]["time"] = 0
    if now - cache["device"]["time"] > cfg["devices"]["refresh"]:
        cache["device"]["dlist"] = cfg["lserver"].scheduler.devices.list()
        cache["device"]["time"] = time.time()
        cache["device"]["redraw"] = True
    if not cache["device"]["redraw"]:
        return
    cfg["dpad"].clear()
    dlist = cache["device"]["dlist"]
    di = 0
    for device in dlist:
        y += 1
        di += 1
        cfg["devices"]["count"] = di
        cfg["devices"]["max"] = di
        dname = device["hostname"]
        if dname not in cache["device"]:
            cache["device"][dname] = {}
            cache["device"][dname]["time"] = 0
        if now - cache["device"][dname]["time"] > cfg["devices"]["refresh"] * 10:
            cache["device"][dname] = cfg["lserver"].scheduler.devices.show(dname)
            cache["device"][dname]["time"] = time.time()
        ddetail = cache["device"][dname]
        if cfg["select"] == di and cfg["tab"] == 1:
            cfg["dpad"].addstr(y, 0, device["hostname"], curses.A_BOLD)
            cfg["sdev"] = dname
        else:
            cfg["dpad"].addstr(y, 0, device["hostname"])
        if device["health"] == 'Bad':
            cfg["dpad"].addstr(y, 26, device["health"], curses.color_pair(1))
        else:
            cfg["dpad"].addstr(y, 26, device["health"])
        cfg["dpad"].addstr(y, 37, device["state"])
        cfg["dpad"].addstr(y, 47, ddetail["worker"])
    cache["device"]["redraw"] = False

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
    y += 1
    cfg["jpad"].addstr(y, 0, "Jobs (refresh %d/%d)" % (now - cache["jobs"]["time"], cfg["jobs"]["refresh"]))
    for job in jlist:
        y += 1
        ji += 1
        cfg["jobs"]["count"] = ji
        jobid = str(job["id"])
        if jobid is int:
            jobid = str(job["id"])
        if cfg["select"] == ji and cfg["tab"] == 2:
            cfg["jpad"].addstr(y, 0, jobid, curses.A_BOLD)
            cfg["sjob"] = jobid
        else:
            cfg["jpad"].addstr(y, 0, jobid)
        if job["health"] == 'Incomplete':
            cfg["jpad"].addstr(y, 6, job["health"], curses.color_pair(1))
        else:
            cfg["jpad"].addstr(y, 6, job["health"])
        cfg["jpad"].addstr(y, 17, job["submitter"])
        if "actual_device" in job and job["actual_device"] != None:
            cfg["jpad"].addstr(y, 29, job["actual_device"])
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

def main(stdscr):
    # Clear screen
    c = 0
    # worker = 0
    # devices = 1
    msg = ""
    cmd = 0
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    vjob = None
    vjob_off = 0
    pad = None

    exit = False
    while not exit:
        now = time.time()
        rows, cols = stdscr.getmaxyx()
        stdscr.addstr(0, 4, str(c))
        stdscr.addstr(0, 10, "Screen %dx%d Lab: %s Select: %d" % (cols, rows, cfg["lab"], cfg["select"]))
        # print help
        stdscr.addstr(0, rows - 2, "HELP: UP DOWN TAB")
        if cfg["tab"] == 1:
            stdscr.addstr(1, 0, "DEVICE HELP: h+[u]")
        if cfg["tab"] == 2:
            stdscr.addstr(1, 0, "JOB HELP: v")
        stdscr.addstr(2, 0, msg)
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
            y_max = rows - 15
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
            y += cfg["devices"]["display"]

        if cfg["jobs"]["enable"]:
            update_jobs()
            cfg["jpad"].refresh(0, 0, y, 0, rows - 1, cols - 1)

        if vjob is not None and pad is None:
            pad = curses.newpad(JOB_MAX_LINE, 5000)
            r = cfg["lserver"].scheduler.job_output(vjob)
            logs = yaml.unsafe_load(r.data)
            y = 2
            for line in logs:
                if y > JOB_MAX_LINE:
                    y += 1
                    continue
                if line['lvl'] == 'info' or line['lvl'] == 'debug' or line['lvl'] == 'target' or line['lvl'] == 'input':
                    if isinstance(line["msg"], list):
                        pad.addstr(y, 0, str(line))
                        y += 1
                        continue
                    pad.addstr(y, 0, line["msg"].rstrip('\0'))
                    y += 1
                    continue
                if line['lvl'] == 'error':
                    pad.addstr(y, 0, line["msg"], curses.color_pair(1))
                    y += 1
                    continue
                if line['lvl'] == 'results':
                    pad.addstr(y, 0, "TEST: %s %s %s" % (line["msg"]["case"], line["msg"]["definition"], line["msg"]["result"]))
                    y += 1
                    # TODO error_msg
                    #pad.addstr(y, 0, str(line))
                    #y += 1
                    continue
                if isinstance(line["msg"], dict):
                    for msg in line["msg"]:
                        pad.addstr(y, 0, msg)
                        y += 1
                elif isinstance(line["msg"], list):
                    pad.addstr(y, 0, str(line))
                    y += 1
                else:
                    pad.addstr(y, 0, line["msg"].rstrip('\0'))
                y += 1
                pad.addstr(y, 0, str(line))
                y += 1
            pad.addstr(0, 0, "LINES: %d" % y)
        if vjob is not None:
            pad.refresh(vjob_off, 0, 2, 55, rows - 1, cols - 1)

        stdscr.refresh()
        #curses.doupdate()
        y += 1
        msg = ""
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
                cfg["devices"]["offset"] -= 5
                if cfg["devices"]["offset"] < 0:
                    cfg["devices"]["offset"] = 0
            else:
                vjob_off -= 100
        elif c == curses.KEY_NPAGE:
            if cfg["tab"] == 1:
                cfg["devices"]["offset"] += 5
                if cfg["devices"]["offset"] > cfg["devices"]["max"] - 20:
                    cfg["devices"]["offset"] = 0
            else:
                vjob_off += 100
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
        elif cmd > 0:
            # want a subcommand
            if cmd == ord('h'):
                cmd = 0
                if c == ord('u'):
                    msg = "Set %s to unknow" % cfg["sdev"]
                    cfg["lserver"].scheduler.devices.update(cfg["sdev"], None, None, None, None, 'UNKNOWN')
                    cache["device"]["time"] = 0
                elif c == ord('m'):
                    msg = "Set %s to maintenance" % cfg["sdev"]
                    cfg["lserver"].scheduler.devices.update(cfg["sdev"], None, None, None, None, 'MAINTENANCE')
                    cache["device"]["time"] = 0
                else:
                    msg = "Invalid health %s" % curses.unctrl(c)
            elif cmd == ord('l'):
                if c == ord('n'):
                    cmd = 0
                    msg = switch_lab()
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
                msg = "Set health to"
            else:
                msg = "Invalid"
                cmd = 0
        elif c == ord('x'):
            cmd = 0
            vjob = None
            if pad != None:
                pad.clear()
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
        elif c == ord('v'):
            if cfg["tab"] == 2:
                msg = "View job %s" % cfg["sjob"]
                vjob = cfg["sjob"]
            else:
                msg = "Invalid"
        if vjob_off < 0:
            vjob_off = 0
            msg = "STOP"
        if cfg["tab"] > 2:
            cfg["tab"] = 0
        if cfg["tab"] == 0 and not cfg["workers"]["enable"]:
            cfg["tab"] = 1
        if c == 27 or c == ord('q'):
            exit = True
        check_limits()

wrapper(main)
