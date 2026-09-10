def render():
    c = new_canvas()
    bg_grad = grad_rad([(0, "#0b1a3a"), (0.5, "#123a6b"), (1, "#0a1e3f")], cx=0.4, cy=0.3, r=0.8)
    add(c, bg_grad)
    bg(c, bg_grad)

    glow_blue = grad_rad([(0, "#4fc3f7"), (0.4, "#1e88e5"), (1, "#0d47a1")], cx=0.5, cy=0.5, r=0.5)
    add(c, glow_blue)
    glow_pink = grad_rad([(0, "#f8bbd0"), (0.5, "#ec407a"), (1, "#ad1457")], cx=0.5, cy=0.5, r=0.5)
    add(c, glow_pink)
    glow_green = grad_rad([(0, "#a5d6a7"), (0.5, "#4caf50"), (1, "#1b5e20")], cx=0.5, cy=0.5, r=0.5)
    add(c, glow_green)

    # Seaweed strands
    for i in range(14):
        x = 30 + i * 36
        h = 120 + (i % 5) * 40
        amp = 15 + (i % 3) * 8
        wv = wave(x, 512, x + 20, 512 - h, amp=amp, periods=2 + (i % 3), fill=None, stroke=glow_green, sw=3)
        add(c, opacity(wv, 0.5 + 0.1 * (i % 4)))

    # Jellyfish 1 - large, center-left
    j1 = group([
        blob(180, 260, 70, wobble=0.15, points=14, fill=glow_pink, stroke=None),
        blob(180, 260, 55, wobble=0.12, points=12, fill="#f48fb1", stroke=None, seed=7),
        blob(180, 260, 40, wobble=0.1, points=10, fill="#fce4ec", stroke=None, seed=3),
    ], translate=(0, 0))
    add(c, glow(j1, blur=12, color="#f48fb1", opacity=0.6))

    # Tentacles for jellyfish 1
    for k in range(8):
        ang = -90 + (k - 3.5) * 12
        x0, y0 = polar(180, 260, 55, ang)
        x1, y1 = polar(180, 260, 110, ang + 10)
        x2, y2 = polar(180, 260, 160, ang - 5)
        x3, y3 = polar(180, 260, 200, ang + 8)
        pb = PathBuilder().move(x0, y0).curve(x1, y1, x2, y2, x3, y3)
        add(c, opacity(path(pb.d(), fill=None, stroke="#f48fb1", sw=2), 0.5))

    # Jellyfish 2 - smaller, right
    j2 = group([
        blob(380, 320, 45, wobble=0.18, points=12, fill=glow_blue, stroke=None),
        blob(380, 320, 35, wobble=0.14, points=10, fill="#90caf9", stroke=None, seed=11),
        blob(380, 320, 25, wobble=0.1, points=8, fill="#e3f2fd", stroke=None, seed=5),
    ], translate=(0, 0))
    add(c, glow(j2, blur=10, color="#90caf9", opacity=0.5))

    for k in range(6):
        ang = -90 + (k - 2.5) * 15
        x0, y0 = polar(380, 320, 35, ang)
        x1, y1 = polar(380, 320, 80, ang + 12)
        x2, y2 = polar(380, 320, 120, ang - 6)
        x3, y3 = polar(380, 320, 150, ang + 10)
        pb = PathBuilder().move(x0, y0).curve(x1, y1, x2, y2, x3, y3)
        add(c, opacity(path(pb.d(), fill=None, stroke="#90caf9", sw=2), 0.4))

    # Jellyfish 3 - tiny, top right
    j3 = group([
        blob(440, 150, 25, wobble=0.2, points=10, fill=glow_pink, stroke=None),
        blob(440, 150, 18, wobble=0.15, points=8, fill="#f8bbd0", stroke=None, seed=2),
    ], translate=(0, 0))
    add(c, glow(j3, blur=8, color="#f8bbd0", opacity=0.4))

    for k in range(5):
        ang = -90 + (k - 2) * 18
        x0, y0 = polar(440, 150, 18, ang)
        x1, y1 = polar(440, 150, 50, ang + 14)
        x2, y2 = polar(440, 150, 80, ang - 8)
        x3, y3 = polar(440, 150, 100, ang + 12)
        pb = PathBuilder().move(x0, y0).curve(x1, y1, x2, y2, x3, y3)
        add(c, opacity(path(pb.d(), fill=None, stroke="#f8bbd0", sw=1.5), 0.4))

    # Bubbles
    for (bx, by, br, op) in [(90, 120, 8, 0.3), (150, 80, 5, 0.25), (300, 60, 10, 0.2), (420, 400, 6, 0.3), (60, 350, 7, 0.2), (250, 450, 9, 0.25)]:
        add(c, opacity(circle(bx, by, br, fill=None, stroke="#b3e5fc", sw=1.5), op))

    # Light rays from top
    ray1 = polygon([(100, 0), (180, 0), (260, 512), (140, 512)], fill="#e3f2fd", stroke=None)
    add(c, opacity(ray1, 0.05))
    ray2 = polygon([(300, 0), (380, 0), (420, 512), (300, 512)], fill="#e3f2fd", stroke=None)
    add(c, opacity(ray2, 0.04))

    # Small particles
    for i in range(30):
        px = (i * 137) % 512
        py = (i * 89) % 512
        pr = 1 + (i % 3)
        add(c, opacity(circle(px, py, pr, fill="#e1f5fe", stroke=None), 0.15 + 0.05 * (i % 4)))

    vignette(c, strength=0.4, color="#020810")
    return to_svg(c)