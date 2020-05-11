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
* x close window (for job window)
* ESC to quit
* space: toggle selection

### in workers tab
TODO set maintenance
### in device tab
* h for set health
** u for unknow
** m for maintenance
### in jobs tab
* v view job
** TODO rerun

## labs.yaml format
```
labs:
  - name: LAVAlab
    lavauri: http://admin:adminpass@127.0.0.1/RPC2
```
