def render():
    c = new_canvas(512, 512)
    bg(c, "#f5f5f0")
    
    # Sky
    add(c, rect(0, 0, 512, 512, fill="#f5f5f0"))
    
    # Sun (red circle)
    add(c, circle(420, 90, 40, fill="#d90429"))
    
    # Black building - tallest
    add(c, rect(100, 80, 120, 432, fill="#2b2d42", stroke="#2b2d42", sw=0))
    # Yellow windows
    for wx in range(115, 205, 22):
        for wy in range(110, 480, 22):
            add(c, rect(wx, wy, 12, 12, fill="#ffd60a"))
    
    # Blue building - middle
    add(c, rect(220, 150, 140, 362, fill="#003049", stroke="#003049", sw=0))
    # White windows
    for wx in range(235, 345, 26):
        for wy in range(170, 480, 26):
            add(c, rect(wx, wy, 16, 16, fill="#f5f5f0"))
    
    # Red building - left short
    add(c, rect(0, 280, 100, 232, fill="#d90429", stroke="#d90429", sw=0))
    # Yellow windows
    for wx in range(10, 90, 16):
        for wy in range(300, 480, 16):
            add(c, rect(wx, wy, 10, 10, fill="#ffd60a"))
    
    # Yellow building - right short
    add(c, rect(360, 320, 152, 192, fill="#ffd60a", stroke="#ffd60a", sw=0))
    # Black windows
    for wx in range(380, 495, 24):
        for wy in range(340, 490, 24):
            add(c, rect(wx, wy, 14, 14, fill="#2b2d42"))
    
    # Blue triangular accent on black building
    add(c, polygon([(100, 80), (160, 20), (220, 80)], fill="#003049", stroke="#003049", sw=0))
    
    # Red triangle on yellow building
    add(c, polygon([(360, 320), (436, 260), (512, 320)], fill="#d90429", stroke="#d90429", sw=0))
    
    # Black horizontal stripe - ground
    add(c, rect(0, 480, 512, 32, fill="#2b2d42", stroke="#2b2d42", sw=0))
    
    # Yellow circle on blue building
    add(c, circle(290, 240, 20, fill="#ffd60a", stroke="#ffd60a", sw=0))
    
    # Red line accent
    add(c, rect(220, 400, 140, 8, fill="#d90429", stroke="#d90429", sw=0))
    
    # Blue vertical accent on yellow building
    add(c, rect(360, 420, 16, 60, fill="#003049", stroke="#003049", sw=0))
    
    # Black small triangle on red building
    add(c, polygon([(50, 280), (50, 220), (0, 280)], fill="#2b2d42", stroke="#2b2d42", sw=0))
    
    return to_svg(c)