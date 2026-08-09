"""Sinh icon.ico cho tool — nút play trên nền gradient tím-xanh, bo góc."""
from PIL import Image, ImageDraw

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# nền gradient chéo (accent xanh -> tím)
c1 = (109, 139, 255)   # #6d8bff
c2 = (155, 109, 255)   # #9b6dff

# gradient dọc
grad = Image.new("RGB", (S, S), c1)
gd = ImageDraw.Draw(grad)
for i in range(S):
    t = i / (S - 1)
    r = int(c1[0] * (1 - t) + c2[0] * t)
    g = int(c1[1] * (1 - t) + c2[1] * t)
    b = int(c1[2] * (1 - t) + c2[2] * t)
    gd.line([(0, i), (S, i)], fill=(r, g, b))

# mặt nạ bo góc
radius = 116
mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)

base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
base.paste(grad, (0, 0), mask)

# tam giác play trắng ở giữa
d2 = ImageDraw.Draw(base)
cx, cy = S // 2, S // 2
w = 150
d2.polygon(
    [(cx - w * 0.62, cy - w), (cx - w * 0.62, cy + w), (cx + w * 0.95, cy)],
    fill=(255, 255, 255, 255),
)

# xuất .ico đa kích thước
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
base.save("icon.ico", format="ICO", sizes=sizes)
base.save("icon.png")
print("wrote icon.ico + icon.png")
