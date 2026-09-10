def render():
    c = new_canvas(512, 512)
    DARK = "#0e1a2b"
    FOG = "#8fa4b5"
    LIGHT = "#f3ead6"

    bg(c, DARK)

    # Soft light beams
    add(c, opacity(polygon([(256, 112), (0, 176), (0, 268)], fill=LIGHT, stroke=None), 0.14))
    add(c, opacity(polygon([(256, 112), (512, 176), (512, 268)], fill=LIGHT, stroke=None), 0.14))

    # Lighthouse tower
    add(c, polygon([(230, 120), (282, 120), (344, 390), (168, 390)], fill=LIGHT, stroke=None))

    # Lantern room
    add(c, rect(214, 120, 84, 3, fill=LIGHT, stroke=None))
    add(c, rect(228, 100, 56, 20, fill=DARK, stroke=None))
    add(c, opacity(circle(256, 108, 32, fill=LIGHT, stroke=None), 0.22))
    add(c, circle(256, 108, 8, fill=LIGHT, stroke=None))

    # Dark tower stripes
    def x_left(y):
        return 230 + (168 - 230) / (390 - 120) * (y - 120)

    def x_right(y):
        return 282 + (344 - 282) / (390 - 120) * (y - 120)

    stripes = []
    for y1, y2 in [(185, 215), (245, 275), (305, 335)]:
        l1, r1 = x_left(y1), x_right(y1)
        l2, r2 = x_left(y2), x_right(y2)
        stripes.append(polygon([(l1, y1), (r1, y1), (r2, y2), (l2, y2)], fill=DARK, stroke=None))
    add(c, stripes)

    # Fog layers
    bands = [
        (
            [(0, 290), (70, 281), (150, 293), (240, 279), (330, 292), (430, 283), (512, 290),
             (512, 318), (420, 314), (310, 325), (200, 313), (100, 319), (0, 314)],
            0.2
        ),
        (
            [(0, 350), (90, 340), (200, 356), (320, 348), (430, 360), (512, 352),
             (512, 392), (380, 382), (280, 396), (170, 382), (70, 390), (0, 378)],
            0.3
        ),
        (
            [(0, 428), (100, 410), (220, 444), (340, 414), (440, 438), (512, 420),
             (512, 486), (420, 472), (300, 478), (180, 466), (60, 472), (0, 462)],
            0.4
        ),
    ]

    for pts, alpha in bands:
        d = smooth(pts, closed=True)
        add(c, opacity(path(d, fill=FOG, stroke=None), alpha))

    return to_svg(c)