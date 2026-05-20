"""
Visual Novel Engine — Pygame
================================
OOP concepts added (naturally, not forced):

  Encapsulation  — Scene, TextState, BgState are classes: data + methods together
  Abstraction    — BaseBackground hides whether the bg is static or animated
  Inheritance    — StaticBackground / AnimatedBackground extend BaseBackground
  Polymorphism   — engine calls bg.get_frame() without knowing which subclass it is
  Decorator      — @clamp(0, 100) on PlayerStats.apply() keeps sanity/anger in range
"""

import pygame
import json
import os
import sys
import functools

WIDTH  = 1280
HEIGHT = 720
FPS    = 60

COLOR_TEXT         = (230, 220, 200)
COLOR_PANEL        = (10, 8, 20, 200)
COLOR_BUTTON       = (30, 25, 50, 220)
COLOR_BUTTON_HOVER = (70, 55, 110, 240)
COLOR_BORDER       = (140, 100, 200)
COLOR_SANITY       = (100, 200, 255)
COLOR_ANGER        = (255, 80,  60)
COLOR_BAR_BG       = (20, 15, 35, 180)

FONT_PATH = None



def clamp(lo, hi):
    """
    Decorator factory.  Usage:

        @clamp(0, 100)
        def apply(self, delta):
            return self.value + delta
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return max(lo, min(hi, result))
        return wrapper
    return decorator



class PlayerStats:
    def __init__(self):
        self.sanity = 100
        self.anger  = 0

    @clamp(0, 100)
    def _clamp_sanity(self, value):
        return value

    @clamp(0, 100)
    def _clamp_anger(self, value):
        return value

    def apply(self, sanity_delta=0, anger_delta=0):
        """Apply stat changes; clamping is automatic via the decorator."""
        self.sanity = self._clamp_sanity(self.sanity + sanity_delta)
        self.anger  = self._clamp_anger(self.anger  + anger_delta)

    def is_mad(self):
        return self.sanity <= 0

    def is_raging(self):
        return self.anger >= 100



class BaseBackground:
    """Abstract base — defines the interface, doesn't implement it."""

    def update(self, dt):
        raise NotImplementedError

    def get_frame(self):
        raise NotImplementedError

    @staticmethod
    def from_scene(scene_data):
        """
        Factory: reads scene_data and returns the right subclass.
        The caller gets a BaseBackground and never needs to switch
        on the type again.
        """
        if "bg_folder" in scene_data:
            return AnimatedBackground(
                scene_data["bg_folder"],
                scene_data.get("bg_fps", 24)
            )
        return StaticBackground(scene_data.get("background", ""))


class StaticBackground(BaseBackground):
    """Encapsulates a single PNG surface.  update() is a no-op."""

    def __init__(self, path):
        self._frame = load_image(path, (WIDTH, HEIGHT))

    def update(self, dt):
        pass   # nothing to advance

    def get_frame(self):
        return self._frame


class AnimatedBackground(BaseBackground):
    """Encapsulates a PNG-sequence with its own frame timer."""

    def __init__(self, folder, fps=24):
        self._frames  = self._load_frames(folder)
        self._delay   = 1000 // fps
        self._index   = 0
        self._timer   = 0

    @staticmethod
    def _load_frames(folder):
        frames = []
        if os.path.isdir(folder):
            files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
            for f in files:
                img = pygame.image.load(os.path.join(folder, f)).convert()
                frames.append(pygame.transform.scale(img, (WIDTH, HEIGHT)))
        if not frames:
            surf = pygame.Surface((WIDTH, HEIGHT))
            surf.fill((20, 15, 35))
            frames.append(surf)
        return frames

    def update(self, dt):
        self._timer += dt
        if self._timer >= self._delay:
            self._timer  = 0
            self._index  = (self._index + 1) % len(self._frames)

    def get_frame(self):
        return self._frames[self._index]


class TextState:
    def __init__(self, text, speed_ms=30):
        self.full_text   = text
        self.chars_shown = 0
        self.timer       = 0
        self.speed_ms    = speed_ms
        self.alpha       = 0
        self.done        = False

    def update(self, dt):
        if self.alpha < 255:
            self.alpha = min(255, self.alpha + int(dt * 0.8))
        if not self.done:
            self.timer += dt
            steps = int(self.timer // self.speed_ms)
            self.timer %= self.speed_ms
            self.chars_shown = min(self.chars_shown + steps, len(self.full_text))
            if self.chars_shown >= len(self.full_text):
                self.done = True

    def skip(self):
        self.chars_shown = len(self.full_text)
        self.done  = True
        self.alpha = 255

    @property
    def visible(self):
        return self.full_text[:self.chars_shown]





class Pager:
    def __init__(self, scene_data):
        if "text_list" in scene_data:
            self.pages = scene_data["text_list"]
        else:
            self.pages = [scene_data.get("text", "")]
        self.index      = 0
        self.text_state = TextState(self.pages[0])

    @property
    def on_last_page(self):
        return self.index == len(self.pages) - 1

    @property
    def total_pages(self):
        return len(self.pages)

    def update(self, dt):
        self.text_state.update(dt)

    def advance(self):
        """Skip animation, or go to next page. Returns True if a new page loaded."""
        if not self.text_state.done:
            self.text_state.skip()
            return False
        if not self.on_last_page:
            self.index     += 1
            self.text_state = TextState(self.pages[self.index])
            return True
        return False



def load_image(path, size=None, placeholder_color=(30, 30, 50)):
    if path and os.path.exists(path):
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.scale(img, size)
        return img
    w, h = size if size else (WIDTH, HEIGHT)
    surf = pygame.Surface((w, h))
    surf.fill(placeholder_color)
    return surf


def wrap_text(text, font, max_width):
    words, lines, current = text.split(), [], ""
    for word in words:
        test = current + " " + word if current else word
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_shadowed_text(screen, text, font, x, y, color, shadow=(0,0,0), offset=2):
    screen.blit(font.render(text, True, shadow), (x + offset, y + offset))
    screen.blit(font.render(text, True, color),  (x, y))


def draw_panel(screen, x, y, width, height, color_rgba, radius=12):
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(surf, color_rgba, (0, 0, width, height), border_radius=radius)
    screen.blit(surf, (x, y))
    pygame.draw.rect(screen, COLOR_BORDER, (x, y, width, height), width=1, border_radius=radius)


def load_scenes(path="scenes.json"):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}



def draw_stats(screen, stats: PlayerStats, font):
    pad_x, pad_y, bar_w, bar_h = 20, 16, 220, 10
    draw_panel(screen, pad_x - 8, pad_y - 8, bar_w + 16, 72, COLOR_BAR_BG, radius=8)
    draw_shadowed_text(screen,
        f"Sanity: {stats.sanity}%   |   Anger: {stats.anger}%",
        font, pad_x, pad_y, COLOR_TEXT)
    for i, (val, color) in enumerate([(stats.sanity, COLOR_SANITY), (stats.anger, COLOR_ANGER)]):
        by = pad_y + 30 + i * 18
        pygame.draw.rect(screen, (40, 35, 60), (pad_x, by, bar_w, bar_h), border_radius=4)
        filled = int(bar_w * val / 100)
        if filled > 0:
            pygame.draw.rect(screen, color, (pad_x, by, filled, bar_h), border_radius=4)



# scene render

def draw_scene(screen, scene_data, pager: Pager, bg: BaseBackground, fonts, mouse,
               stats: PlayerStats):
    # Background — polymorphic call; works for Static and Animated equally
    screen.blit(bg.get_frame(), (0, 0))

    # Character sprite
    char_path = scene_data.get("character", "")
    if char_path:
        screen.blit(load_image(char_path, (320, 480), (0,0,0)),
                    (WIDTH // 2 - 160, HEIGHT - 480 - 120))

    # Dialogue panel
    panel_x, panel_y, panel_w, panel_h = 40, HEIGHT - 240, WIDTH - 80, 230
    alpha = pager.text_state.alpha
    draw_panel(screen, panel_x, panel_y, panel_w, panel_h,
               (*COLOR_PANEL[:3], int(COLOR_PANEL[3] * alpha / 255)))

    # Name
    name = scene_data.get("name", "")
    if name:
        draw_shadowed_text(screen, name, fonts["name"], panel_x + 20, panel_y + 14, COLOR_BORDER)

    # Dialogue text
    lines   = wrap_text(pager.text_state.visible, fonts["text"], panel_w - 40)
    start_y = panel_y + (50 if name else 20)
    for i, line in enumerate(lines[:4]):
        draw_shadowed_text(screen, line, fonts["text"], panel_x + 20, start_y + i * 36, COLOR_TEXT)

    # Page counter
    if pager.total_pages > 1:
        counter = f"{pager.index + 1} / {pager.total_pages}"
        draw_shadowed_text(screen, counter, fonts["button"],
                           panel_x + panel_w - 80, panel_y + panel_h - 30, COLOR_BORDER)

    # Buttons
    active_buttons = []
    btn_w, btn_h, gap = 340, 44, 10
    btn_y = HEIGHT - 58

    if pager.text_state.done:
        if not pager.on_last_page:
            rect = pygame.Rect((WIDTH - btn_w) // 2, btn_y, btn_w, btn_h)
            active_buttons.append((rect, {"__action__": "next"}))
            btn_color = COLOR_BUTTON_HOVER if rect.collidepoint(mouse) else COLOR_BUTTON
            draw_panel(screen, rect.x, btn_y, btn_w, btn_h, btn_color, radius=8)
            pygame.draw.rect(screen, COLOR_BORDER, rect, width=1, border_radius=8)
            label = fonts["button"].render("Next  ▶", True, COLOR_TEXT)
            screen.blit(label, (rect.x + (btn_w - label.get_width()) // 2, btn_y + 10))
        else:
            choices = scene_data.get("choices", [])
            total_w = len(choices) * btn_w + (len(choices) - 1) * gap
            start_x = (WIDTH - total_w) // 2
            for i, choice in enumerate(choices):
                bx   = start_x + i * (btn_w + gap)
                rect = pygame.Rect(bx, btn_y, btn_w, btn_h)
                active_buttons.append((rect, choice))
                btn_color = COLOR_BUTTON_HOVER if rect.collidepoint(mouse) else COLOR_BUTTON
                draw_panel(screen, bx, btn_y, btn_w, btn_h, btn_color, radius=8)
                pygame.draw.rect(screen, COLOR_BORDER, rect, width=1, border_radius=8)
                label = fonts["button"].render(choice["text"], True, COLOR_TEXT)
                screen.blit(label, (bx + (btn_w - label.get_width()) // 2, btn_y + 10))

    draw_stats(screen, stats, fonts["button"])
    return active_buttons



#  loop v razgovore

def run_game():
    pygame.init()
    pygame.display.set_caption("Autonomous Ecosystem — Demo")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock  = pygame.time.Clock()

    if FONT_PATH and os.path.exists(FONT_PATH):
        font_text   = pygame.font.Font(FONT_PATH, 26)
        font_name   = pygame.font.Font(FONT_PATH, 30)
        font_button = pygame.font.Font(FONT_PATH, 22)
    else:
        font_text   = pygame.font.SysFont("segoeui", 26)
        font_name   = pygame.font.SysFont("segoeui", 30, bold=True)
        font_button = pygame.font.SysFont("segoeui", 22)

    fonts      = {"text": font_text, "name": font_name, "button": font_button}
    all_scenes = load_scenes()

    stats = PlayerStats()   # encapsulated sanity + anger

    # ── Scene Manager ──
    def enter_scene(scene_id):
        data  = all_scenes[scene_id]
        pager = Pager(data)
        bg    = BaseBackground.from_scene(data)   # factory → polymorphic bg
        return data, pager, bg

    current_id            = "start"
    scene_data, pager, bg = enter_scene(current_id)
    active_buttons        = []

    while True:
        dt    = clock.tick(FPS)
        mouse = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    pager.advance()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not pager.text_state.done:
                    pager.text_state.skip()
                else:
                    for rect, choice in active_buttons:
                        if not rect.collidepoint(mouse):
                            continue

                        if choice.get("__action__") == "next":
                            pager.advance()
                            break

                        next_scene = choice["next"]
                        if next_scene == "__exit__":
                            pygame.quit(); sys.exit()

                        # Apply stat changes — @clamp handles the bounds automatically
                        stats.apply(
                            sanity_delta=choice.get("sanity_change", 0),
                            anger_delta =choice.get("anger_change",  0)
                        )

                        # Check critical states
                        if stats.is_mad() and "madness_end" in all_scenes:
                            next_scene = "madness_end"
                        elif stats.is_raging() and "rage_end" in all_scenes:
                            next_scene = "rage_end"

                        current_id            = next_scene
                        scene_data, pager, bg = enter_scene(current_id)
                        break

        pager.update(dt)
        bg.update(dt)   # polymorphic: Static does nothing, Animated advances frame

        active_buttons = draw_scene(screen, scene_data, pager, bg, fonts, mouse, stats)
        pygame.display.flip()


if __name__ == "__main__":
    run_game()
