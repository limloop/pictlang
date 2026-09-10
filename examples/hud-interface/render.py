def render():
    c = new_canvas(512, 512)
    bg(c, "#000000")
    
    # Glow gradients
    g_green = grad_rad([(0, "#00ff88"), (0.6, "#00ff88"), (1, "#00ff8800")], cx=0.5, cy=0.5, r=0.5)
    add(c, g_green)
    g_magenta = grad_rad([(0, "#ff00ff"), (0.6, "#ff00ff"), (1, "#ff00ff00")], cx=0.5, cy=0.5, r=0.5)
    add(c, g_magenta)
    g_cyan = grad_rad([(0, "#00ffff"), (0.6, "#00ffff"), (1, "#00ffff00")], cx=0.5, cy=0.5, r=0.5)
    add(c, g_cyan)
    
    # Main grid
    grid_el = grid(0, 0, 512, 512, 16, 16, fill=None, stroke="#00ff8833", sw=1)
    add(c, grid_el)
    
    # Hexagonal pattern
    hex_pts = []
    for i in range(6):
        ang = 60 * i - 30
        hex_pts.append(polar(256, 256, 120, ang))
    hex_el = polygon(hex_pts, fill=None, stroke="#00ffff", sw=2)
    add(c, glow(hex_el, blur=6, color="#00ffff", opacity=0.8))
    
    # Inner hexagon
    hex_pts2 = []
    for i in range(6):
        ang = 60 * i - 30
        hex_pts2.append(polar(256, 256, 80, ang))
    hex_el2 = polygon(hex_pts2, fill=None, stroke="#ff00ff", sw=2)
    add(c, glow(hex_el2, blur=8, color="#ff00ff", opacity=0.6))
    
    # Circuit traces
    trace_pts = [(0, 256), (80, 256), (120, 200), (180, 200), (220, 160), (256, 160)]
    trace = polyline(trace_pts, stroke="#00ff88", sw=2, fill=None)
    add(c, glow(trace, blur=4, color="#00ff88", opacity=0.7))
    
    trace_pts2 = [(512, 256), (432, 256), (392, 312), (332, 312), (292, 352), (256, 352)]
    trace2 = polyline(trace_pts2, stroke="#00ffff", sw=2, fill=None)
    add(c, glow(trace2, blur=4, color="#00ffff", opacity=0.7))
    
    # Corner brackets
    for (cx, cy, rot) in [(20, 20, 0), (492, 20, 90), (492, 492, 180), (20, 492, 270)]:
        bracket = group([
            line(0, 0, 30, 0, stroke="#00ff88", sw=3),
            line(0, 0, 0, 30, stroke="#00ff88", sw=3),
            line(0, 30, 0, 20, stroke="#00ff88", sw=3),
            line(30, 0, 20, 0, stroke="#00ff88", sw=3),
        ], translate=(cx, cy), rotate=rot)
        add(c, glow(bracket, blur=4, color="#00ff88", opacity=0.8))
    
    # Glitch text effect
    text_glitch = group([
        text(256, 240, "SYS.ONLINE", size=28, fill="#00ff88", family="monospace"),
        text(258, 242, "SYS.ONLINE", size=28, fill="#ff00ff", family="monospace"),
        text(254, 238, "SYS.ONLINE", size=28, fill="#00ffff", family="monospace"),
    ])
    add(c, glow(text_glitch, blur=6, color="#00ff88", opacity=0.5))
    
    # Status bars
    for i, (y, color, label) in enumerate([(280, "#00ff88", "PWR"), (300, "#00ffff", "SIG"), (320, "#ff00ff", "CPU")]):
        bar_bg = rect(180, y, 152, 8, fill="#000000", stroke=color, sw=1)
        add(c, bar_bg)
        bar_fill = rect(182, y+2, 100 + i*20, 4, fill=color, stroke=None, sw=0)
        add(c, glow(bar_fill, blur=3, color=color, opacity=0.8))
        add(c, text(170, y+8, label, size=10, fill=color, family="monospace", anchor="end"))
    
    # Radar sweep
    radar = group([
        circle(256, 400, 40, fill=None, stroke="#00ff88", sw=1),
        circle(256, 400, 25, fill=None, stroke="#00ff88", sw=1),
        circle(256, 400, 10, fill=None, stroke="#00ff88", sw=1),
        line(256, 400, 296, 380, stroke="#00ff88", sw=2),
        line(256, 400, 256, 360, stroke="#00ff88", sw=1),
        line(256, 400, 216, 400, stroke="#00ff88", sw=1),
    ])
    add(c, glow(radar, blur=4, color="#00ff88", opacity=0.6))
    
    # Blips on radar
    add(c, circle(270, 390, 3, fill="#ff00ff", stroke=None, sw=0))
    add(c, circle(240, 410, 2, fill="#00ffff", stroke=None, sw=0))
    
    # Data readout
    data_lines = [
        "> INIT OK",
        "> LINK: STABLE",
        "> TARGET: 3",
        "> MODE: ACTIVE",
    ]
    for i, line_text in enumerate(data_lines):
        color = ["#00ff88", "#00ffff", "#ff00ff", "#00ff88"][i]
        add(c, text(60, 460 + i*14, line_text, size=11, fill=color, family="monospace", anchor="start"))
    
    # Decorative dots
    for i in range(8):
        x = 60 + i * 55
        add(c, circle(x, 430, 2, fill="#00ff88", stroke=None, sw=0))
    
    # Crosshair center
    cross = group([
        line(246, 256, 266, 256, stroke="#ff00ff", sw=1),
        line(256, 246, 256, 266, stroke="#ff00ff", sw=1),
        circle(256, 256, 5, fill=None, stroke="#ff00ff", sw=1),
    ])
    add(c, glow(cross, blur=3, color="#ff00ff", opacity=0.8))
    
    # Vignette
    vignette(c, strength=0.6, color="#000000")
    
    return to_svg(c)