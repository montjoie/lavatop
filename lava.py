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
cfg["devices"]["select"] = []
cfg["devices"]["sort"] = 0
cfg["devtypes"] = {}
cfg["devtypes"]["refresh"] = 60
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

wl = {}

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
    global cache
    # closes some lab specific window
    if "viewjob" in wl:
        del wl["viewjob"]
    if "workers" in wl:
        del wl["workers"]
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
        cache = {}
        if not "DEVICENAME_LENMAX" in new:
            cfg["lab"]["DEVICENAME_LENMAX"] = 24
        if not "DEVTYPE_LENMAX" in new:
            cfg["lab"]["DEVTYPE_LENMAX"] = 24
        if not "WKNAME_LENMAX" in new:
            cfg["lab"]["WKNAME_LENMAX"] = 10
        if not "JOB_LENMAX" in lab:
            cfg["lab"]["JOB_LENMAX"] = 5
        if not "USER_LENMAX" in lab:
            cfg["lab"]["USER_LENMAX"] = 10
        cfg["devices"]["select"] = []
        if "workers" in wl:
            wl["workers"].select = None
        cfg["swk"] = None
        cfg["sdev"] = None
        debug("Switched to %s\n" % new["name"])
        return "Switched to %s" % new["name"]
    return "switch error"

switch_lab(True)





class lava_win:
    def __init__(self):
        self.sx = 0
        self.sy = 0
        self.win = None
        self.pad = None
        self.count = 0
        self.offset = 0
        self.display = 0
        self.redraw = False
        # current selection
        self.cselect = 1
        self.select = None
        # for cache
        self.dt_time = 0
        self.d_time = 0
        self.wtime = 0

    def setup(self, sx, sy, wx, wy):
        # recreate window if size change
        if self.sx != sx:
            self.win = None
        if self.sy != sy:
            self.win = None
        self.sx = sx
        self.sy = sy
        self.wx = wx
        self.wy = wy
        if self.win == None:
            debug("Create window %dx%d at %x,%d\n" % (sx, sy, wx, wy))
            self.win = curses.newwin(sx, sy, wy, wx)

    def fill(self, cache, lserver, cfg):
        return False

    def handle_key(c):
        return False

class win_devtypes(lava_win):
    def fill(self, cache, lserver, cfg):
        if self.pad == None:
            self.pad = curses.newpad(100, 200)
        # check need of redraw
        if not self.redraw and self.dt_time == cache["devtypes"]["time"]:
            return

        self.win.erase()
        self.pad.erase()
        self.redraw = False
        self.count = 0
        y = 1
        self.dt_time = cache["devtypes"]["time"]
        for devtype in cache["devtypes"]["dlist"]:
            x = 0
            self.count += 1
            self.pad.addstr(y, x, devtype["name"])
            if cfg["lab"]["DEVTYPE_LENMAX"] < len(devtype["name"]):
                cfg["lab"]["DEVTYPE_LENMAX"] = len(devtype["name"])
                self.dt_time = 0
            x += cfg["lab"]["DEVTYPE_LENMAX"] + 1
            self.pad.addstr(y, x, "%d" % devtype["devices"])
            # TODO ? installed template
            x += 6
            dc = 0
            for device in cache["device"]["dlist"]:
                if device["type"] == devtype["name"] and device["state"] != 'Running' \
                    and device["health"] != 'Bad' \
                    and device["health"] != 'Maintenance' \
                    and device["health"] != 'Retired':
                    dc += 1
            if dc > 0:
                self.pad.addstr(y, x, "%d" % dc)
            x += 5
            dc = 0
            for device in cache["device"]["dlist"]:
                if device["type"] == devtype["name"] and (device["health"] == 'Bad'\
                    or device["health"] == 'Maintenance' \
                    or device["health"] == 'Retired'):
                    dc += 1
            if dc > 0:
                self.pad.addstr(y, x, "%d" % dc)
            x += 8
            dc = 0
            for device in cache["device"]["dlist"]:
                if device["type"] == devtype["name"] and device["state"] == 'Running':
                    dc += 1
            if dc > 0:
                self.pad.addstr(y, x, "%d" % dc)
            y += 1
        # decoration: 2, title 1
        self.display = self.sy - 2 - 1
        if self.display > self.count:
            self.display = self.count

    def show(self, cfg):
        # title
        x = 1
        self.win.addstr(1, x, "Viewing %d-%d/%d" % (self.offset + 1, self.offset + self.display, self.count))
        x += cfg["lab"]["DEVTYPE_LENMAX"] + 1
        self.win.addstr(1, x, "Count")
        x += 6
        self.win.addstr(1, x, "Idle")
        x += 5
        self.win.addstr(1, x, "Offline")
        x += 8
        self.win.addstr(1, x, "Busy")

        self.win.box("|", "-")
        self.win.noutrefresh()
        self.pad.noutrefresh(self.offset, 0, self.wy + 2, self.wx + 1, self.wx + self.sx - 4, self.wy + self.sy - 4)

    def handle_key(self, c):
        # this window should handle PG UP PG DOWN
        if c == curses.KEY_PPAGE:
            self.offset -= 5
            if self.offset < 0:
                self.offset = 0
            self.redraw = True
            return True
        if c == curses.KEY_NPAGE:
            self.offset += 5
            if self.offset > self.count:
                self.offset = self.count
            self.redraw = True
            return True
        return False

# end of device types #

class win_view_job(lava_win):
    def choose_job(self, jobid):
        self.jobid = jobid

    def fill(self, cache, lserver, cfg):
        # TODO handle cache expire
        if not self.jobid in cache:
            r = lserver.scheduler.job_output(self.jobid)
            logs = yaml.unsafe_load(r.data)
            cache[self.jobid] = logs
            self.redraw = True
        else:
            logs = cache[self.jobid]

        # check need of redraw
        if not self.redraw:
            return

        self.win.erase()
        self.redraw = False
        y = 1
        self.count = 4
        #TODO change 500
        linew = 500
        for line in logs:
            if line['lvl'] == 'info' or line['lvl'] == 'debug' or line['lvl'] == 'target' or line['lvl'] == 'input':
                if isinstance(line["msg"], list):
                    self.count += 1
                    if linew < len(line["msg"]):
                        linew = len(line["msg"])
                elif isinstance(line["msg"], dict):
                    for msg in line["msg"]:
                        if linew < len(line["msg"]):
                            linew = len(msg)
                        self.count += 1
                else:
                    if linew < len(line["msg"]):
                        linew = len(line["msg"])
                    self.count += 1
            elif line['lvl'] == 'results':
                self.count += 1
                if "error_msg" in line["msg"]:
                    for eline in line["msg"]["error_msg"].split("\n"):
                        self.count += 1
                        if linew < len(eline):
                            linew = len(eline)
            else:
                self.count += 1
        # TODO verify count/line change
        if self.pad == None:
            debug("Create job pad of %dx%d\n" % (self.count, linew))
            self.pad = curses.newpad(self.count, linew)
        self.pad.erase()
        y = 2
        for line in logs:
            if y > self.count:
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
                    self.pad.addstr(y, 0, str(line))
                    y += 1
                    continue
                self.pad.addstr(y, 0, line["msg"].replace('\0', ''), curses.color_pair(color))
                y += 1
                continue
            if line['lvl'] == 'error':
                self.pad.addstr(y, 0, line["msg"], curses.color_pair(1))
                y += 1
                continue
            if line['lvl'] == 'results':
                self.pad.addstr(y, 0, "TEST: %s %s %s" % (line["msg"]["case"], line["msg"]["definition"], line["msg"]["result"]))
                y += 1
                if "error_msg" in line["msg"]:
                    self.pad.addstr(y, 0, line["msg"]["error_msg"], curses.color_pair(1))
                    y += 1
                continue
            if isinstance(line["msg"], dict):
                for msg in line["msg"]:
                    self.pad.addstr(y, 0, msg)
                    y += 1
            elif isinstance(line["msg"], list):
                self.pad.addstr(y, 0, str(line))
                y += 1
            else:
                self.pad.addstr(y, 0, line["msg"].rstrip('\0'))
                y += 1
        # decoration: 2, title 1
        self.display = self.sy - 2 - 1
        if self.display > self.count:
            self.display = self.count

    def show(self, cfg):
        # title
        x = 1
        self.win.addstr(1, x, "Viewing %s %d-%d/%d" % (self.jobid, self.offset + 1, self.offset + self.display, self.count))

        self.win.box("|", "-")
        self.win.noutrefresh()
        self.pad.noutrefresh(self.offset, 0, self.wy + 2, self.wx + 1, self.wx + self.sx - 4, self.wy + self.sy - 4)

    def handle_key(self, c):
        # this window should handle PG_UP PG_DOWN UP DOWN HOME END
        if c == curses.KEY_UP:
            self.offset -= 1
            if self.offset < 0:
                self.offset = 0
            self.redraw = True
            return True
        if c == curses.KEY_PPAGE:
            self.offset -= 20
            if self.offset < 0:
                self.offset = 0
            self.redraw = True
            return True
        if c == curses.KEY_DOWN:
            self.offset += 1
            if self.offset > self.count:
                self.offset = self.count
            self.redraw = True
            return True
        if c == curses.KEY_NPAGE:
            self.offset += 20
            if self.offset > self.count:
                self.offset = self.count
            self.redraw = True
            return True
        return False

# end of view job  #

class win_workers(lava_win):
    def fill(self, cache, lserver, cfg):
        y = 0
        wmax = len(cache["workers"]["wlist"])
        # if the number of worker changed, recreate window
        if self.count < wmax:
            self.pad = None
        if self.pad == None:
            self.pad = curses.newpad(wmax + 1, 200)
            self.redraw = True
        if not self.redraw:
            return
        self.redraw = False
        self.win.erase()
        self.pad.erase()
        wlist = cache["workers"]["wlist"]
        wi = 0
        if self.select == None:
            self.select = []
            for worker in wlist:
                self.select.append(worker)
        for worker in wlist:
            wdet = cache["workers"]["detail"][worker]["wdet"]
            wi += 1
            self.count = wi
            if worker in self.select:
                self.pad.addstr(y, 0, "[x]")
            else:
                self.pad.addstr(y, 0, "[ ]")
            x = 4
            if self.cselect == wi and cfg["tab"] == 0:
                self.pad.addstr(y, x, worker, curses.A_BOLD)
                cfg["swk"] = worker
            else:
                self.pad.addstr(y, x, worker)
            x += cfg["lab"]["WKNAME_LENMAX"]
            if wdet["state"] == 'Offline':
                self.pad.addstr(y, x, wdet["state"], curses.color_pair(1))
            elif wdet["state"] == 'Online':
                self.pad.addstr(y, x, wdet["state"], curses.color_pair(2))
            else:
                self.pad.addstr(y, x, wdet["state"])
            x += 10
            if wdet["health"] == 'Active':
                self.pad.addstr(y, x, wdet["health"], curses.color_pair(2))
            else:
                self.pad.addstr(y, x, wdet["health"], curses.color_pair(1))
            x+= 7
            if "version" in wdet and wdet["version"] != None:
                self.pad.addstr(y, x, wdet["version"])
            y += 1
        # TODO job_limit:
        # TODO last_ping:
        self.display = self.count

    def show(self, cfg):
        # title
        self.win.addstr(0, 0, "Workers %d-%d/%d" % (self.offset + 1, self.offset + self.display, self.count))

        #self.win.box("|", "-")
        self.win.noutrefresh()
        self.pad.noutrefresh(self.offset, 0, self.wy + 1, self.wx, self.wx + self.sx, self.wy + self.sy)

    def handle_key(self, c):
        # this window should handle UP DOWN = space
        if c == curses.KEY_UP:
            self.cselect -= 1
            if self.cselect < 0:
                self.cselect = 0
            self.redraw = True
            cache["device"]["redraw"] = True
            return True
        if c == curses.KEY_DOWN:
            self.cselect += 1
            if self.cselect > self.count:
                self.cselect = self.count
            self.redraw = True
            cache["device"]["redraw"] = True
            return True
        if c == ord("="):
            self.select = []
            self.select.append(cfg["swk"])
            cache["device"]["redraw"] = True
            self.redraw = True
            return True
        if c == ord(" "):
            if cfg["swk"] in self.select:
                self.select.remove(cfg["swk"])
            else:
                self.select.append(cfg["swk"])
            cache["device"]["redraw"] = True
            self.redraw = True
            return True
        return False
# end of view worker  #

def update_devices():
    now = time.time()
    y = -1
    if cfg["dpad"] == None:
        cfg["dpad"] = curses.newpad(100, cfg["cols"])
    if not cache["device"]["redraw"]:
        return
    cache["device"]["redraw"] = False
    cfg["dpad"].erase()
    dlist = cache["device"]["dlist"]
    #fdebug = open("alldevices", "w")
    #yaml.dump(dlist, fdebug)
    #fdebug.close()
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

        if "workers" in wl and wl["workers"].select != None and ddetail["worker"] not in wl["workers"].select:
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
        #TODO current_job

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

# TODO get limits here
def update_cache():
    now = time.time()
    if not "device" in cache:
        cache["device"] = {}
        cache["device"]["time"] = 0
    if now - cache["device"]["time"] > cfg["devices"]["refresh"]:
        cache["device"]["dlist"] = cfg["lserver"].scheduler.devices.list(True, True)
        cache["device"]["time"] = time.time()
        cache["device"]["redraw"] = True
    if not "workers" in cache:
        cache["workers"] = {}
        cache["workers"]["detail"] = {}
        cache["workers"]["time"] = 0
    if now - cache["workers"]["time"] > cfg["workers"]["refresh"]:
        cache["workers"]["wlist"] = cfg["lserver"].scheduler.workers.list()
        cache["workers"]["time"] = time.time()
    for worker in cache["workers"]["wlist"]:
        #debug("Refresh %s\n" % worker)
        if len(worker) > cfg["lab"]["WKNAME_LENMAX"]:
            cfg["lab"]["WKNAME_LENMAX"] = len(worker) + 1
            debug("WKNAME_LENMAX set to %d\n" % cfg["lab"]["WKNAME_LENMAX"])
        if not worker in cache["workers"]["detail"]:
            cache["workers"]["detail"][worker] = {}
            cache["workers"]["detail"][worker]["time"] = 0
        if now - cache["workers"]["detail"][worker]["time"] > 10:
            cache["workers"]["detail"][worker]["time"] = time.time()
            cache["workers"]["detail"][worker]["wdet"] = cfg["lserver"].scheduler.workers.show(worker)
    if not "devtypes" in cache:
        cache["devtypes"] = {}
        cache["devtypes"]["time"] = 0
    if now - cache["devtypes"]["time"] > cfg["devtypes"]["refresh"]:
        cache["devtypes"]["dlist"] = cfg["lserver"].scheduler.device_types.list()
        cache["devtypes"]["time"] = time.time()

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
        update_cache()

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
            if not "workers" in wl:
                wl["workers"] = win_workers()
            wl["workers"].setup(cfg["lab"]["WKNAME_LENMAX"] + 21, 100, 0, y)
            wl["workers"].fill(cache, cfg["lserver"], cfg)
            wl["workers"].show(cfg)
            y += wl["workers"].display + 2

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
            cfg["wjobs"].erase()
            cfg["wjobs"].box("|", "-")
            cfg["wjobs"].addstr(1, 1, "Jobs %d-%d/%d (refresh %d/%d)" % (
                cfg["jobs"]["offset"] + 1,
                cfg["jobs"]["display"] + cfg["jobs"]["offset"],
                cfg["jobs"]["count"],
                now - cache["jobs"]["time"],
                cfg["jobs"]["refresh"]))
            cfg["wjobs"].noutrefresh()
            cfg["jpad"].noutrefresh(cfg["jobs"]["offset"], 0, 4+2, cfg["sc"] + 1, rows - 2, cols - 2)

        stdscr.noutrefresh()

        if "viewjob" in wl:
            wl["viewjob"].setup(cfg["rows"] - 8, cfg["cols"] - 8, 4, 4)
            wl["viewjob"].fill(cache, cfg["lserver"], cfg)
            wl["viewjob"].show(cfg)

        if "devtypes" in wl:
            wl["devtypes"].setup(cfg["rows"] - 8, cfg["cols"] - 8, 4, 4)
            wl["devtypes"].fill(cache, cfg["lserver"], cfg)
            wl["devtypes"].show(cfg)

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
        if "devtypes" in wl:
            if wl["devtypes"].handle_key(c):
                c = -1
        if c > 0 and "viewjob" in wl:
            if wl["viewjob"].handle_key(c):
                c = -1
        if c > 0 and "workers" in wl and cfg["tab"] == 0:
            if wl["workers"].handle_key(c):
                c = -1
        if c == curses.KEY_UP:
            cfg["select"] -= 1
            if cfg["tab"] == 1:
                cache["device"]["redraw"] = True
            else:
                cache["jobs"]["redraw"] = True
        elif c == curses.KEY_DOWN:
            cfg["select"] += 1
            if cfg["tab"] == 1:
                cache["device"]["redraw"] = True
            else:
                cache["jobs"]["redraw"] = True
        elif c == curses.KEY_PPAGE:
            if cfg["tab"] == 1:
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
            if cfg["tab"] == 1:
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
        elif c == ord(" "):
            if cfg["tab"] == 1:
                if cfg["sdev"] in cfg["devices"]["select"]:
                    cfg["devices"]["select"].remove(cfg["sdev"])
                else:
                    cfg["devices"]["select"].append(cfg["sdev"])
                cache["device"]["redraw"] = True
                if "devselect" in cfg["jobs"]["filter"]:
                    cache["jobs"]["redraw"] = True
        elif c == curses.KEY_F1:
            if "devtypes" in wl:
                del wl["devtypes"]
            else:
                wl["devtypes"] = win_devtypes()
        elif c == 9:
            # TAB
            if cfg["tab"] == 0:
                cfg["tab"] = 1
                cache["device"]["redraw"] = True
                if "workers" in wl:
                    wl["workers"].redraw = True
                msg = "Switched to devices tab"
            elif cfg["tab"] == 1:
                cfg["tab"] = 2
                cache["device"]["redraw"] = True
                cache["jobs"]["redraw"] = True
                msg = "Switched to jobs tab"
            else:
                cfg["tab"] = 0
                if "workers" in wl:
                    wl["workers"].redraw = True
                cache["jobs"]["redraw"] = True
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
            elif "devtypes" in wl:
                del wl["devtypes"]
            elif "viewjob" in wl:
                del wl["viewjob"]
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
                wl["viewjob"] = win_view_job()
                wl["viewjob"].choose_job(cfg["sjob"])
            else:
                msg = "Invalid"
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
