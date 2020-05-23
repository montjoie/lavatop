#!/usr/bin/env python3

import curses
from curses import wrapper
import xmlrpc.client
import threading
import time
import yaml

cache = {}
cfg = {}
cfg["workers"] = {}
cfg["workers"]["enable"] = True
cfg["workers"]["refresh"] = 60
cfg["devices"] = {}
cfg["devices"]["enable"] = True
cfg["devices"]["refresh"] = 20
cfg["devices"]["sort"] = 0
cfg["devtypes"] = {}
cfg["devtypes"]["refresh"] = 60
cfg["jobs"] = {}
cfg["jobs"]["enable"] = True
cfg["jobs"]["refresh"] = 20
# where = 0 on right of screen, 1 is in classic tab
cfg["jobs"]["where"] = 0
cfg["jobs"]["title"] = True
cfg["jobs"]["titletrunc"] = True
cfg["jobs"]["filter"] = []
cfg["jobs"]["maxfetch"] = 200

cfg["tab"] = 0
cfg["select"] = 1
cfg["sjob"] = None
cfg["dpad"] = None
# selected worker
cfg["swk"] = None
# selected device
cfg["sdev"] = None
# current lab
cfg["lab"] = None
# the status window
cfg["swin"] = None

#second colum start
cfg["sc"] = 0

wl = {}

lock = {}
lock["jobs"] = threading.Lock()
lock["workers"] = threading.Lock()
lock["devices"] = threading.Lock()
lock["device_types"] = threading.Lock()
lock["cache"] = threading.Lock()
state = 0

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
        lock["cache"].acquire
        lock["workers"].acquire
        lock["devices"].acquire
        lock["jobs"].acquire
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
        if "workers" in wl:
            wl["workers"].select = None
        if "devices" in wl:
            wl["devices"].select = None
        cfg["swk"] = None
        cfg["sdev"] = None
        debug("Switched to %s\n" % new["name"])
        lock["workers"].acquire
        lock["devices"].acquire
        lock["jobs"].acquire
        lock["cache"].release
        return "Switched to %s" % new["name"]
    return "switch error"

switch_lab(True)





class lava_win:
    def __init__(self):
        self.sx = 0
        self.sy = 0
        self.wx = 0
        self.wy = 0
        self.win = None
        self.pad = None
        self.count = 0
        self.offset = 0
        self.display = 0
        self.redraw = False
        self.box = False
        self.close = False
        # current selection
        self.cselect = 1
        self.select = None

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
            debug("Create window %dx%d at %d,%d\n" % (sx, sy, wx, wy))
            self.win = curses.newwin(sy, sx, wy, wx)
            self.redraw = True
            self.pad = None

    def fill(self, cache, lserver, cfg):
        return False

    def handle_key(c):
        return False

class win_devtypes(lava_win):
    def fill(self, cache, lserver, cfg):
        if self.pad == None:
            self.pad = curses.newpad(100, 200)
        if not "devtypes" in cache:
            return
        # check need of redraw
        if not self.redraw:
            return

        lock["device_types"].acquire()
        self.win.erase()
        self.pad.erase()
        self.redraw = False
        self.count = 0
        y = 1
        for devtype in cache["devtypes"]["dlist"]:
            x = 0
            self.count += 1
            self.pad.addstr(y, x, devtype["name"])
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
        lock["device_types"].release()
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
        self.pad.noutrefresh(self.offset, 0, self.wy + 2, self.wx + 1,
            self.wy + self.sy - 4,
            self.wx + self.sx - 4)

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
        self.pad.noutrefresh(self.offset, 0, self.wy + 2, self.wx + 1,
            self.wy + self.sy - 2,
            self.wx + self.sx - 2)

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
        if "workers" not in cache or "wlist" not in cache["workers"]:
            self.win.erase()
            self.win.addstr(1, 1, "Loading")
            return
        if not lock["workers"].acquire(False):
            return
        y = 0
        wmax = len(cache["workers"]["wlist"])
        # if the number of worker changed, recreate window
        if self.count < wmax:
            self.pad = None
        if self.pad == None:
            self.pad = curses.newpad(wmax + 1, 200)
            self.redraw = True
        if not self.redraw:
            lock["workers"].release()
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
        lock["workers"].release()
        # TODO job_limit:
        # TODO last_ping:
        self.display = self.count

    def show(self, cfg):
        # title
        self.win.addstr(0, 0, "Workers %d-%d/%d" % (self.offset + 1, self.offset + self.display, self.count))

        #self.win.box("|", "-")
        self.win.noutrefresh()
        if self.pad != None:
            self.pad.noutrefresh(self.offset, 0, self.wy + 1, self.wx,
                self.wy + self.sy,
                self.wx + self.sx)

    def handle_key(self, c):
        # this window should handle UP DOWN = space
        if c == curses.KEY_UP:
            self.cselect -= 1
            if self.cselect < 1:
                self.cselect = 1
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

class win_devices(lava_win):
    def fill(self, cache, lserver, cfg):
        if self.pad == None:
            # TODO chnage 100
            self.pad = curses.newpad(100, self.sx)
            self.redraw = True
        if not self.redraw:
            return
        if "device" not in cache or "dlist" not in cache["device"]:
            self.win.erase()
            self.pad.addstr(2, 2, "Loading")
            return
        if "workers" not in cache:
            self.win.erase()
            self.pad.addstr(2, 2, "Loading")
            return
        if not lock["workers"].acquire(False):
            return
        lock["devices"].acquire()
        self.pad.erase()
        self.win.erase()
        dlist = cache["device"]["dlist"]
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

        if self.select == None:
            self.select = []
        di = 0
        y = 0
        for device in dlist:
            dname = device["hostname"]
            ddetail = cache["device"][dname]

            if "workers" in wl and wl["workers"].select != None and ddetail["worker"] not in wl["workers"].select:
                continue
            x = 4
            di += 1
            self.count = di
            if dname in self.select:
                self.pad.addstr(y, 0, "[x]")
            else:
                self.pad.addstr(y, 0, "[ ]")
            if self.cselect == di and cfg["tab"] == 1:
                self.pad.addstr(y, x, device["hostname"], curses.A_BOLD)
                cfg["sdev"] = dname
            else:
                self.pad.addstr(y, x, device["hostname"])
            x += cfg["lab"]["DEVICENAME_LENMAX"] + 1
            if device["health"] == 'Bad':
                self.pad.addstr(y, x, device["health"], curses.color_pair(1))
            elif device["health"] == 'Good':
                self.pad.addstr(y, x, device["health"], curses.color_pair(2))
            elif device["health"] == 'Maintenance':
                self.pad.addstr(y, x, device["health"], curses.color_pair(3))
            else:
                self.pad.addstr(y, x, device["health"])
            x += 12
            if device["state"] == 'Running':
                self.pad.addstr(y, x, device["state"], curses.color_pair(2))
            elif device["state"] == 'Idle':
                self.pad.addstr(y, x, device["state"], curses.color_pair(3))
            else:
                self.pad.addstr(y, x, device["state"])
            x += 9
            wkname = ddetail["worker"]
            if cache["workers"]["detail"][wkname]["wdet"]["state"] == 'Offline':
                self.pad.addstr(y, x, wkname, curses.color_pair(1))
            elif cfg["tab"] == 0 and cfg["swk"] != None and wkname in cfg["swk"]:
                self.pad.addstr(y, x, wkname, curses.A_BOLD)
            else:
                self.pad.addstr(y, x, wkname)
            x += cfg["lab"]["WKNAME_LENMAX"]
            if x > cfg["sc"]:
                cfg["sc"] = x
            #TODO current_job
            y += 1
        lock["workers"].release()
        lock["devices"].release()
        self.display = self.sy - 1
        self.box = False
        if self.box:
            self.display -= 2
        if self.display > self.count:
            self.display = self.count
    # show devices
    def show(self, cfg):
        ox = 0
        oy = 0
        if self.box:
            ox = 1
            oy = 1
        # title
        self.win.addstr(ox, oy, "Devices %d-%d/%d %d %s" % (
            self.offset + 1, self.offset + self.display, self.count,
            self.cselect,
            cfg["sdev"]))

        if self.box:
            self.win.box("|", "-")
        self.win.noutrefresh()
        self.pad.noutrefresh(self.offset, 0,
            self.wy + oy + 1,
            self.wx + ox,
            self.wy + self.sy - oy - 1,
            self.wx + self.sx - ox - 1)

    # handle key for devices
    def handle_key(self, c):
        h = False
        # this window should handle UP DOWN = space PGUP PGDOWN
        if c == curses.KEY_UP:
            self.cselect -= 1
            if self.cselect < 1:
                self.cselect = 1
            self.redraw = True
            h = True
            if "joblist" in wl:
                wl["joblist"].redraw = True
        if c == curses.KEY_DOWN:
            self.cselect += 1
            if self.cselect > self.count:
                self.cselect = self.count
            self.redraw = True
            h = True
            if "joblist" in wl:
                wl["joblist"].redraw = True
        if c == ord("="):
            self.select = []
            self.select.append(cfg["sdev"])
            self.redraw = True
            if "joblist" in wl:
                wl["joblist"].redraw = True
            return True
        if c == ord(" "):
            if cfg["sdev"] in self.select:
                self.select.remove(cfg["sdev"])
            else:
                self.select.append(cfg["sdev"])
            self.redraw = True
            if "joblist" in wl:
                wl["joblist"].redraw = True
            return True
        # select go out of view
        if self.cselect > self.display + self.offset:
            self.offset += 1
        if self.cselect <= self.offset and self.offset > 0:
            self.offset -= 1
        return h
# end of devices  #

class win_jobs(lava_win):
    def fill(self, cache, lserver, cfg):
        y = 0
        if self.pad == None:
            if cfg["jobs"]["where"] == 1:
                w = cfg["cols"] - 2
            else:
                w = cfg["cols"] - cfg["sc"] - 2
            debug("Create jobpad w=%d\n" % w)
            self.pad = curses.newpad(cfg["jobs"]["maxfetch"] * 2, w)
            self.redraw = True
        ji = 0
        if not "jobs" in cache or not "jlist" in cache["jobs"]:
            self.pad.erase()
            self.win.erase()
            self.pad.addstr(1, 1, "Loading")
            return
        if not self.redraw:
            return
        if not lock["jobs"].acquire(False):
            return
        self.redraw = False
        self.win.erase()
        self.pad.erase()
        jlist = cache["jobs"]["jlist"]
        for job in jlist:
            # filter
            if "devselect" in cfg["jobs"]["filter"]:
                if "actual_device" not in job:
                    continue
                if job["actual_device"] not in wl["devices"].select:
                    continue
            x = 0
            ji += 1
            self.count = ji
            jobid = str(job["id"])
            if jobid is int:
                jobid = str(job["id"])
            if self.cselect == ji and cfg["tab"] == 2:
                self.pad.addstr(y, x, jobid, curses.A_BOLD)
                cfg["sjob"] = jobid
            else:
                self.pad.addstr(y, x, jobid)
            x += cfg["lab"]["JOB_LENMAX"] + 1
            if job["health"] == 'Incomplete':
                self.pad.addstr(y, x, job["health"], curses.color_pair(1))
            elif job["health"] == 'Complete':
                self.pad.addstr(y, x, job["health"], curses.color_pair(2))
            elif job["health"] == 'Unknown':
                self.pad.addstr(y, x, job["health"], curses.color_pair(3))
            else:
                self.pad.addstr(y, x, job["health"])
            x += 11
            self.pad.addstr(y, x, job["submitter"])
            x += cfg["lab"]["USER_LENMAX"] + 1
            if "actual_device" in job and job["actual_device"] != None:
                if cfg["tab"] == 1 and cfg["sdev"] != None and job["actual_device"] in cfg["sdev"]:
                    self.pad.addstr(y, x, job["actual_device"], curses.A_BOLD)
                else:
                    self.pad.addstr(y, x, job["actual_device"])
            else:
                # print the device type instead
                self.pad.addstr(y, x, job["device_type"])
            x += cfg["lab"]["DEVICENAME_LENMAX"]
            if cfg["jobs"]["title"]:
                if cfg["jobs"]["titletrunc"]:
                    spaces = self.sx - x - 2
                    #if spaces > len(job["description"]):
                    #    spaces = len(job["description"])
                    self.pad.addstr(y, x, job["description"][:spaces])
                    y += 1
                else:
                    self.pad.addstr(y, x, job["description"])
                    y += 2
            else:
                y += 1
        lock["jobs"].release()
        self.box = True
        self.display = self.sy - 1
        if self.box:
            self.display -= 2
        if self.display > self.count:
            self.display = self.count

    def show(self, cfg):
        decorative = True
        ox = 0
        oy = 0
        if self.box:
            ox = 1
            oy = 1
        # title
        self.win.addstr(ox, oy, "Jobs %s %d %d-%d/%d" % (cfg["sjob"], self.cselect,
            self.offset + 1, self.offset + self.display, self.count))

        if self.box:
            self.win.box("|", "-")
        self.win.noutrefresh()
        #debug("Pad to %dx%d %dx%d screen=%dx%d\n" % (
        #    self.wx, self.wy + 1,
        #    self.wx + self.sx, self.wy + self.sy,
        #    cfg["cols"], cfg["rows"]
        #    ))
        self.pad.noutrefresh(self.offset, 0,
            self.wy + oy + 1,
            self.wx + ox,
            self.wy + self.sy - oy - 1,
            self.wx + self.sx - ox - 1)

    def handle_key(self, c):
        h = False
        # this window should handle UP DOWN NPAGE PPAGE
        if c == curses.KEY_UP:
            self.cselect -= 1
            if self.cselect < 1:
                self.cselect = 1
            self.redraw = True
            h = True
        if c == curses.KEY_DOWN:
            self.cselect += 1
            if self.cselect > self.count:
                self.cselect = self.count
            self.redraw = True
            h = True
        if c == curses.KEY_PPAGE:
            self.offset -= 20
            if self.offset < 0:
                self.offset = 0
            self.redraw = True
            h = True
        if c == curses.KEY_NPAGE:
            self.offset += 20
            if self.offset > self.count - self.display:
                self.offset = self.count - self.display
            if self.cselect < self.offset:
                self.cselect = self.offset
            self.redraw = True
            h = True
        # select go out of view
        if self.cselect > self.display + self.offset:
            self.offset += 1
        if self.cselect <= self.offset and self.offset > 0:
            self.offset -= 1
        return h
# end of view worker  #

class win_options(lava_win):
    def fill(self, cache, lserver, cfg):
        self.win.erase()
        if cfg["workers"]["enable"]:
            self.win.addstr(2, 2, "[x] show [w]orkers tab")
        else:
            self.win.addstr(2, 2, "[ ] show [w]orkers tab")
        if cfg["devices"]["enable"]:
            self.win.addstr(3, 2, "[x] show [d]evices tab")
        else:
            self.win.addstr(3, 2, "[ ] show [d]evices tab")
        if cfg["jobs"]["enable"]:
            self.win.addstr(4, 2, "[x] show jobs tab")
        else:
            self.win.addstr(4, 2, "[ ] show jobs tab")
        if cfg["jobs"]["where"] == 1:
            self.win.addstr(5, 2, "[ ] display jobs on the right")
        else:
            self.win.addstr(5, 2, "[x] display jobs on the right")
        if cfg["jobs"]["title"]:
            self.win.addstr(6, 2, "[x] display job [t]itle")
        else:
            self.win.addstr(6, 2, "[ ] display job [t]itle")
        if cfg["jobs"]["titletrunc"]:
            self.win.addstr(7, 2, "[x] [T]runcate job title")
        else:
            self.win.addstr(7, 2, "[ ] [T]runcate job title")
        self.win.addstr(2, 30, "DEVICENAME_LENMAX: %d" % cfg["lab"]["DEVICENAME_LENMAX"])
        self.win.addstr(3, 30, "Job fetch max: %d" % cfg["jobs"]["maxfetch"])

    def show(self, cfg):
        self.box = True
        ox = 0
        oy = 0
        if self.box:
            ox = 1
            oy = 1
        # title
        self.win.addstr(ox, oy, "Jobs %s %d %d-%d/%d" % (cfg["sjob"], self.cselect,
            self.offset + 1, self.offset + self.display, self.count))

        if self.box:
            self.win.box("|", "-")
        self.win.noutrefresh()

    def handle_key(self, c):
        if c == ord('+'):
            cfg["jobs"]["maxfetch"] += 100
            if "joblist" in wl:
                wl["joblist"].pad = None
                wl["joblist"].redraw = True
            return True
        if c == ord('-'):
            cfg["jobs"]["maxfetch"] += 100
            if cfg["jobs"]["maxfetch"] < 100:
                cfg["jobs"]["maxfetch"] = 100
            if "joblist" in wl:
                wl["joblist"].pad = None
                wl["joblist"].redraw = True
            return True
        if c == ord('1'):
            if "devselect" in cfg["jobs"]["filter"]:
                cfg["jobs"]["filter"].remove("devselect")
            else:
                cfg["jobs"]["filter"].append("devselect")
            return True
        if c == ord("x"):
            self.close = True
            return True
        return False
# end option

class win_filters(lava_win):
    def fill(self, cache, lserver, cfg):
        self.win.erase()
        self.win.addstr(2, 2, "Devices filter")
        if "devselect" in cfg["jobs"]["filter"]:
            self.win.addstr(3, 2, "1 [x] Filter jobs from selected devices")
            if "joblist" in wl:
                wl["joblist"].redraw = True
        else:
            self.win.addstr(3, 2, "1 [ ] Filter jobs from selected devices")
        self.win.addstr(20, 2, "Jobs filter")

    def show(self, cfg):
        self.box = True
        ox = 0
        oy = 0
        if self.box:
            ox = 1
            oy = 1
        # title
        self.win.addstr(ox, oy, "Jobs %s %d %d-%d/%d" % (cfg["sjob"], self.cselect,
            self.offset + 1, self.offset + self.display, self.count))

        if self.box:
            self.win.box("|", "-")
        self.win.noutrefresh()
        #self.pad.noutrefresh(self.offset, 0,
        #    self.wy + oy + 1,
        #    self.wx + ox,
        #    self.wy + self.sy - oy - 1,
        #    self.wx + self.sx - ox - 1)

    def handle_key(self, c):
        if c == ord('1'):
            if "devselect" in cfg["jobs"]["filter"]:
                cfg["jobs"]["filter"].remove("devselect")
            else:
                cfg["jobs"]["filter"].append("devselect")
            return True
        if c == ord("x"):
            self.close = True
            return True
        return False
# end filters


# TODO get limits here
def update_cache():
    global state
    now = time.time()

    lock["devices"].acquire()
    state = 1
    if not "device" in cache:
        cache["device"] = {}
        cache["device"]["time"] = 0
    if now - cache["device"]["time"] > cfg["devices"]["refresh"]:
        cache["device"]["dlist"] = cfg["lserver"].scheduler.devices.list(True, True)
        cache["device"]["time"] = time.time()
        if "devices" in wl:
            wl["devices"].redraw = True
    for device in cache["device"]["dlist"]:
        dname = device["hostname"]
        if dname not in cache["device"]:
            cache["device"][dname] = {}
            cache["device"][dname]["time"] = 0
        if now - cache["device"][dname]["time"] > cfg["devices"]["refresh"] * 10:
            cache["device"][dname] = cfg["lserver"].scheduler.devices.show(dname)
            cache["device"][dname]["time"] = time.time()
            if "devices" in wl:
                wl["devices"].redraw = True
        if len(dname) > cfg["lab"]["DEVICENAME_LENMAX"]:
            cfg["lab"]["DEVICENAME_LENMAX"] = len(dname)
    lock["devices"].release()

    lock["workers"].acquire()
    state = 2
    if not "workers" in cache:
        cache["workers"] = {}
        cache["workers"]["detail"] = {}
        cache["workers"]["time"] = 0
    if now - cache["workers"]["time"] > cfg["workers"]["refresh"]:
        cache["workers"]["wlist"] = cfg["lserver"].scheduler.workers.list()
        cache["workers"]["time"] = time.time()
        if "workers" in wl:
            wl["workers"].redraw = True
    for worker in cache["workers"]["wlist"]:
        #debug("Refresh %s\n" % worker)
        if len(worker) > cfg["lab"]["WKNAME_LENMAX"]:
            cfg["lab"]["WKNAME_LENMAX"] = len(worker) + 1
            debug("WKNAME_LENMAX set to %d\n" % cfg["lab"]["WKNAME_LENMAX"])
        if not worker in cache["workers"]["detail"]:
            cache["workers"]["detail"][worker] = {}
            cache["workers"]["detail"][worker]["time"] = 0
        if now - cache["workers"]["detail"][worker]["time"] > 10:
            cache["workers"]["detail"][worker]["wdet"] = cfg["lserver"].scheduler.workers.show(worker)
            cache["workers"]["detail"][worker]["time"] = time.time()
            if "workers" in wl:
                wl["workers"].redraw = True
    lock["workers"].release()

    state = 3
    if "jobs" not in cache:
        cache["jobs"] = {}
        cache["jobs"]["time"] = 0
        cache["jobs"]["jlist"] = []
    if now - cache["jobs"]["time"] > cfg["jobs"]["refresh"]:
        offset = 0
        fl = []
        while offset < cfg["jobs"]["maxfetch"]:
            l = cfg["lserver"].scheduler.jobs.list(None, None, offset, 100, None, True)
            #debug("Job load %d\n" % offset)
            fl += l
            offset += 100
        lock["jobs"].acquire()
        cache["jobs"]["jlist"] = fl
        cache["jobs"]["time"] = time.time()
        lock["jobs"].release()
        if "joblist" in wl:
            wl["joblist"].redraw = True
    for job in cache["jobs"]["jlist"]:
        jobid = str(job["id"])
        if len(jobid) > cfg["lab"]["JOB_LENMAX"]:
            cfg["lab"]["JOB_LENMAX"] = len(jobid) + 1
        if len(job["submitter"]) > cfg["lab"]["USER_LENMAX"]:
            cfg["lab"]["USER_LENMAX"] = len(job["submitter"])

    if not "devtypes" in cache:
        cache["devtypes"] = {}
        cache["devtypes"]["time"] = 0
    lock["device_types"].acquire()
    if now - cache["devtypes"]["time"] > cfg["devtypes"]["refresh"]:
        cache["devtypes"]["dlist"] = cfg["lserver"].scheduler.device_types.list()
        cache["devtypes"]["time"] = time.time()
        if "devtypes" in wl:
            wl["devtypes"].redraw = True
    lock["device_types"].release()
    for devtype in cache["devtypes"]["dlist"]:
        if cfg["lab"]["DEVTYPE_LENMAX"] < len(devtype["name"]):
            cfg["lab"]["DEVTYPE_LENMAX"] = len(devtype["name"])

def cache_thread():
    while "exit" not in cache:
        lock["cache"].acquire
        update_cache()
        lock["cache"].release
        time.sleep(2)

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

    ct = threading.Thread(target=cache_thread)
    ct.start()

    exit = False
    while not exit:
        now = time.time()
        rows, cols = stdscr.getmaxyx()
        cfg["rows"] = rows
        cfg["cols"] = cols
        #update_cache()

        for winwin in list(wl):
            if wl[winwin].close:
                del wl[winwin]

        if cfg["swin"] == None:
            cfg["swin"] = curses.newwin(3, cfg["cols"], 0, 0)
        cfg["swin"].erase()
        cfg["swin"].addstr(0, 0, "Screen %dx%d Lab: %s Select: %d HELP: UP DOWN TAB [Q]uit [f]ilters [o]ptions state=%d" % (cols, rows, cfg["lab"]["name"], cfg["select"], state))
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
            # TODO the + 30 is for cleaning
            wl["workers"].setup(cfg["lab"]["WKNAME_LENMAX"] + 21 + 30, 100, 0, y)
            wl["workers"].fill(cache, cfg["lserver"], cfg)
            wl["workers"].show(cfg)
            y += wl["workers"].display + 2

        # devices
        if cfg["devices"]["enable"]:
            if not "devices" in wl:
                wl["devices"] = win_devices()
            if cfg["jobs"]["enable"] and cfg["jobs"]["where"] == 1:
                y_max = rows - 15
            else:
                y_max = rows
            wl["devices"].setup(cfg["cols"] - 1, y_max - y, 0, y)
            wl["devices"].fill(cache, cfg["lserver"], cfg)
            wl["devices"].show(cfg)
            y += wl["devices"].display + 2

        if cfg["sc"] > cfg["cols"] - 65 and cfg["jobs"]["where"] == 0:
            # too small, cannot print jobs on right
            cfg["jobs"]["where"] = 1
            msg = "TOO SMALL %d %d %d" % (cfg["sc"], cfg["cols"], cfg["cols"] - 30)
            debug("Downgrade to no job windows sc=%d cols=%d\n" % (cfg["sc"], cfg["cols"]))
        if cfg["jobs"]["enable"]:
            if not "joblist" in wl:
                wl["joblist"] = win_jobs()
            if cfg["jobs"]["where"] == 0:
                # setup on "second column"
                wl["joblist"].setup(cfg["cols"] - cfg["sc"]  - 1, cfg["rows"] - 3, cfg["sc"], 3)
                wl["joblist"].fill(cache, cfg["lserver"], cfg)
                wl["joblist"].show(cfg)
            else:
                # setup on bottom
                if rows -y - 1 > 0:
                    wl["joblist"].setup(cfg["cols"], rows - y, 0, y)
                    wl["joblist"].fill(cache, cfg["lserver"], cfg)
                    wl["joblist"].show(cfg)

        stdscr.noutrefresh()

        if "viewjob" in wl:
            wl["viewjob"].setup(cfg["cols"] - 8, cfg["rows"] - 8, 4, 4)
            wl["viewjob"].fill(cache, cfg["lserver"], cfg)
            wl["viewjob"].show(cfg)

        if "devtypes" in wl:
            wl["devtypes"].setup(cfg["cols"] - 8, cfg["rows"] - 8, 4, 4)
            wl["devtypes"].fill(cache, cfg["lserver"], cfg)
            wl["devtypes"].show(cfg)

        if "filters" in wl:
            wl["filters"].setup(cfg["cols"] - 8, cfg["rows"] - 8, 4, 4)
            wl["filters"].fill(cache, cfg["lserver"], cfg)
            wl["filters"].show(cfg)

        if "options" in wl:
            wl["options"].setup(cfg["cols"] - 8, cfg["rows"] - 8, 4, 4)
            wl["options"].fill(cache, cfg["lserver"], cfg)
            wl["options"].show(cfg)

        curses.doupdate()

        #curses.doupdate()
        y += 1
        #msg = ""
        c = stdscr.getch()
        if "options" in wl:
            if wl["options"].handle_key(c):
                c = -1
        if "filters" in wl:
            if wl["filters"].handle_key(c):
                c = -1
        if "devtypes" in wl:
            if wl["devtypes"].handle_key(c):
                c = -1
        if c > 0 and "viewjob" in wl:
            if wl["viewjob"].handle_key(c):
                c = -1
        if c > 0 and "workers" in wl and cfg["tab"] == 0:
            if wl["workers"].handle_key(c):
                c = -1
        if c > 0 and "joblist" in wl and cfg["tab"] == 2:
            if wl["joblist"].handle_key(c):
                c = -1
        if c > 0 and "devices" in wl and cfg["tab"] == 1:
            if wl["devices"].handle_key(c):
                c = -1
        if c == curses.KEY_F1:
            if "devtypes" in wl:
                del wl["devtypes"]
            else:
                wl["devtypes"] = win_devtypes()
        elif c == 9:
            # TAB
            if cfg["tab"] == 0:
                cfg["tab"] = 1
                if "devices" in wl:
                    wl["devices"].redraw = True
                if "workers" in wl:
                    wl["workers"].redraw = True
                msg = "Switched to devices tab"
            elif cfg["tab"] == 1:
                cfg["tab"] = 2
                if "devices" in wl:
                    wl["devices"].redraw = True
                if "joblist" in wl:
                    wl["joblist"].redraw = True
                msg = "Switched to jobs tab"
            else:
                cfg["tab"] = 0
                if "workers" in wl:
                    wl["workers"].redraw = True
                if "joblist" in wl:
                    wl["joblist"].redraw = True
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
                    if "devices" in wl:
                        wl["devices"].redraw = True
                elif c == ord('h'):
                    msg = "Sort by health"
                    cfg["devices"]["sort"] = 1
                    if "devices" in wl:
                        wl["devices"].redraw = True
                elif c == ord('s'):
                    msg = "Sort by state"
                    cfg["devices"]["sort"] = 2
                    if "devices" in wl:
                        wl["devices"].redraw = True
                else:
                    cmd = 0
                    msg = "Invalid sort"
            else:
                cmd = 0
                msg = "Invalid subcomand %s" % curses.unctrl(c)
        elif c == ord('f'):
            if "filters" not in wl:
                wl["filters"] = win_filters()
            else:
                del wl["filters"]
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
            if "options" not in wl:
                wl["options"] = win_options()
            else:
                del wl["options"]
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
            if "devtypes" in wl:
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
            if "joblist" in wl:
                wl["joblist"].redraw = True
        elif c == ord('T'):
            cfg["jobs"]["titletrunc"] = not cfg["jobs"]["titletrunc"]
            if "joblist" in wl:
                wl["joblist"].redraw = True
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
                exit = True
                cache["exit"] = True
                ct.join()
    # this is exit
    if cfg["debug"] != None:
        cfg["debug"].close()

wrapper(main)
