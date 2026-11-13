define e = Character("Eileen", color="#c8ffc8")

label start:
    scene bg cafe
    show eileen happy at left
    e "Welcome to A Cat Cafe!"

    menu:
        "Say hi.":
            jump polite
        "Stay quiet.":
            jump shy

label polite:
    e "That's kind of you to say."
    jump day1

label shy:
    e "..."
    jump day1

label day1:
    hide eileen
    # A construct outside the supported subset (attribute access in a
    # condition) — should be flagged, not crash the parse.
    if some_condition.attr:
        "This branch is not reachable; the condition can't be evaluated."
    call ending
    return

label ending:
    "The end."
    return
