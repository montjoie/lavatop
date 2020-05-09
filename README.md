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
* ESC to quit

### in workers tab
### in device tab
* h for set health
** u for unknow
** m for maintenance
### in jobs tab
* v view job

## labs.yaml format
```
labs:
  - name: LAVAlab
    lavauri: http://admin:adminpass@127.0.0.1/RPC2
```
