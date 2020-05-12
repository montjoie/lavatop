# LAVA manager in ncurses

## Commands
In all tab:
* UP DOWN
* TAB for cycle tabs
* w toggle workers tab
* d toggle device tab
* j togge jobs tab
* r refresh current tab
* R refresh all tabs
* x close window (for job window) or cancel current command
* ESC to quit
* space: toggle selection

### in workers tab
TODO set maintenance
### in device tab
* h for set health then u for unknow, m for maintenance
* a select all in view (TODO)
* A select all (TODO)
* s sort view (sort s for State, h for Health, n for Name)
### in jobs tab
* v view job
** TODO rerun

### in job windows
PAGE UP
PAGE DOWN

## labs.yaml format
```
labs:
  - name: LAVAlab
    lavauri: http://admin:token@127.0.0.1/RPC2
```
