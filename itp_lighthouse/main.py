"""
Visual Novel Engine — Pygame
================================
New in this version: "text_list" support.
A scene can have either:
  "text":      "single string"            <- works exactly as before
  "text_list": ["line 1", "line 2", ...]  <- engine steps through them with a Next button;
                                             choices appear only after the last line.
Everything else (background, name, sanity/anger, PNG sequences) is unchanged.
"""

import pygame
import json
import os
import sys

# ─────────────────────────────────────────────
#  GAME SETTINGS
# ─────────────────────────────────────────────
WIDTH  = 1280
HEIGHT = 720
FPS    = 60

COLOR_TEXT         = (230, 220, 200)
COLOR_SHADOW       = (0, 0, 0)
COLOR_PANEL        = (10, 8, 20, 200)
COLOR_BUTTON       = (30, 25, 50, 220)
COLOR_BUTTON_HOVER = (70, 55, 110, 240)
COLOR_BORDER       = (140, 100, 200)
COLOR_SANITY       = (100, 200, 255)
COLOR_ANGER        = (255, 80,  60)
COLOR_BAR_BG       = (20, 15, 35, 180)

FONT_PATH = None

# ─────────────────────────────────────────────
#  FALLBACK SCENE DATA
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
#  LOAD SCENES FROM JSON
# ─────────────────────────────────────────────
def load_scenes(path="scenes.json"):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)


# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────
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


def load_animation_frames(folder, anim_fps=24):
    frames = []
    if os.path.isdir(folder):
        files = sorted([f for f in os.listdir(folder) if f.lower().endswith(".png")])
        for file in files:
            img = pygame.image.load(os.path.join(folder, file)).convert()
            frames.append(pygame.transform.scale(img, (WIDTH, HEIGHT)))
    if not frames:
        surf = pygame.Surface((WIDTH, HEIGHT))
        surf.fill((20, 15, 35))
        frames.append(surf)
    return frames, 1000 // anim_fps


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


def draw_shadowed_text(screen, text, font, x, y, color, shadow=(0, 0, 0), offset=2):
    screen.blit(font.render(text, True, shadow), (x + offset, y + offset))
    screen.blit(font.render(text, True, color),  (x, y))


def draw_panel(screen, x, y, width, height, color_rgba, radius=12):
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(surf, color_rgba, (0, 0, width, height), border_radius=radius)
    screen.blit(surf, (x, y))
    pygame.draw.rect(screen, COLOR_BORDER, (x, y, width, height), width=1, border_radius=radius)


# ─────────────────────────────────────────────
#  TEXT STATE  (typewriter for ONE string)
# ─────────────────────────────────────────────
def create_text_state(text):
    """Typewriter state for a single text string."""
    return {
        "full_text":   text,
        "chars_shown": 0,
        "timer":       0,
        "speed_ms":    30,
        "alpha":       0,
        "done":        False
    }


def update_text(state, dt):
    if state["alpha"] < 255:
        state["alpha"] = min(255, state["alpha"] + int(dt * 0.8))
    if not state["done"]:
        state["timer"] += dt
        steps = int(state["timer"] // state["speed_ms"])
        state["timer"] %= state["speed_ms"]
        state["chars_shown"] = min(state["chars_shown"] + steps, len(state["full_text"]))
        if state["chars_shown"] >= len(state["full_text"]):
            state["done"] = True
    return state


def skip_animation(state):
    state["chars_shown"] = len(state["full_text"])
    state["done"]  = True
    state["alpha"] = 255
    return state


# ─────────────────────────────────────────────
#  TEXT-LIST STATE  ← NEW
#  Wraps multiple typewriter states into one
#  sequential pager.
# ─────────────────────────────────────────────
def create_pager_state(scene_data):
    """
    Returns a pager dict that works for BOTH scene formats:
      - "text"      → treated as a single-item list internally
      - "text_list" → list of strings stepped through with Next
    Fields:
      pages        – list of strings
      page_index   – which page is currently shown (0-based)
      text_state   – typewriter state for the current page
      on_last_page – True when the player has reached the final page
    """
    if "text_list" in scene_data:
        pages = scene_data["text_list"]
    else:
        pages = [scene_data.get("text", "")]

    return {
        "pages":        pages,
        "page_index":   0,
        "text_state":   create_text_state(pages[0]),
        "on_last_page": len(pages) == 1   # single-page scenes are already on last page
    }


def advance_pager(pager):
    """
    Called when the player clicks Next (or Space/Enter) on a multi-page scene.
    If the current page's typewriter is still running → skip it.
    If it's done and there are more pages → move to the next page.
    Returns True if the pager actually advanced to a new page.
    """
    ts = pager["text_state"]

    # Step 1: finish the current typewriter animation first
    if not ts["done"]:
        skip_animation(ts)
        return False   # didn't advance — just revealed the text

    # Step 2: move to the next page if one exists
    next_index = pager["page_index"] + 1
    if next_index < len(pager["pages"]):
        pager["page_index"] = next_index
        pager["text_state"] = create_text_state(pager["pages"][next_index])
        pager["on_last_page"] = (next_index == len(pager["pages"]) - 1)
        return True   # advanced to a new page

    return False  # already on the last page, nothing to advance


def update_pager(pager, dt):
    pager["text_state"] = update_text(pager["text_state"], dt)
    return pager


# ─────────────────────────────────────────────
#  BACKGROUND STATE
# ─────────────────────────────────────────────
def create_bg_state(scene_data):
    if "bg_folder" in scene_data:
        fps = scene_data.get("bg_fps", 24)
        frames, delay = load_animation_frames(scene_data["bg_folder"], fps)
        return {"frames": frames, "current_frame": 0, "timer": 0, "delay": delay, "animated": True}
    img = load_image(scene_data.get("background", ""), (WIDTH, HEIGHT))
    return {"frames": [img], "current_frame": 0, "timer": 0, "delay": 9999, "animated": False}


def update_bg(bg_state, dt):
    if bg_state["animated"]:
        bg_state["timer"] += dt
        if bg_state["timer"] >= bg_state["delay"]:
            bg_state["timer"] = 0
            bg_state["current_frame"] = (bg_state["current_frame"] + 1) % len(bg_state["frames"])
    return bg_state


def get_bg_frame(bg_state):
    return bg_state["frames"][bg_state["current_frame"]]


# ─────────────────────────────────────────────
#  HUD
# ─────────────────────────────────────────────
def draw_stats(screen, sanity, anger, font):
    pad_x, pad_y, bar_w, bar_h = 20, 16, 220, 10
    draw_panel(screen, pad_x - 8, pad_y - 8, bar_w + 16, 72, COLOR_BAR_BG, radius=8)
    draw_shadowed_text(screen, f"Sanity: {sanity}%   |   Anger: {anger}%", font, pad_x, pad_y, COLOR_TEXT)
    for i, (val, color) in enumerate([(sanity, COLOR_SANITY), (anger, COLOR_ANGER)]):
        by = pad_y + 30 + i * 18
        pygame.draw.rect(screen, (40, 35, 60), (pad_x, by, bar_w, bar_h), border_radius=4)
        filled = int(bar_w * val / 100)
        if filled > 0:
            pygame.draw.rect(screen, color, (pad_x, by, filled, bar_h), border_radius=4)


# ─────────────────────────────────────────────
#  SCENE RENDERING
# ─────────────────────────────────────────────
def draw_scene(screen, scene_data, pager, bg_state, fonts, mouse, sanity=100, anger=0):
    """
    Renders one frame. Returns list of active (rect, choice_dict) tuples.

    Button logic:
      - text_list scenes: show "Next" on all pages except the last;
        show choices only on the last page (and only when typewriter is done).
      - text scenes: show choices as soon as typewriter is done (same as before).
    """
    # 1. Background
    screen.blit(get_bg_frame(bg_state), (0, 0))

    # 2. Character sprite
    char_path = scene_data.get("character", "")
    if char_path:
        screen.blit(load_image(char_path, (320, 480), (0, 0, 0)),
                    (WIDTH // 2 - 160, HEIGHT - 480 - 120))

    # 3. Dialogue panel
    panel_x, panel_y, panel_w, panel_h = 40, HEIGHT - 240, WIDTH - 80, 230
    alpha = pager["text_state"]["alpha"]
    draw_panel(screen, panel_x, panel_y, panel_w, panel_h,
               (*COLOR_PANEL[:3], int(COLOR_PANEL[3] * alpha / 255)))

    # 4. Character name
    name = scene_data.get("name", "")
    if name:
        draw_shadowed_text(screen, name, fonts["name"], panel_x + 20, panel_y + 14, COLOR_BORDER)

    # 5. Dialogue text (typewriter)
    ts = pager["text_state"]
    visible = ts["full_text"][:ts["chars_shown"]]
    lines   = wrap_text(visible, fonts["text"], panel_w - 40)
    start_y = panel_y + (50 if name else 20)
    for i, line in enumerate(lines[:4]):
        draw_shadowed_text(screen, line, fonts["text"], panel_x + 20, start_y + i * 36, COLOR_TEXT)

    # 6. Page counter for text_list scenes  (e.g. "2 / 5")
    total_pages = len(pager["pages"])
    if total_pages > 1:
        counter = f"{pager['page_index'] + 1} / {total_pages}"
        draw_shadowed_text(screen, counter, fonts["button"],
                           panel_x + panel_w - 80, panel_y + panel_h - 30, COLOR_BORDER)

    # 7. Buttons
    active_buttons = []
    btn_w, btn_h, gap = 340, 44, 10
    btn_y = HEIGHT - 58

    text_done     = ts["done"]
    on_last_page  = pager["on_last_page"]

    if text_done:
        if not on_last_page:
            # ── NEXT button (intermediate pages) ──
            rect = pygame.Rect((WIDTH - btn_w) // 2, btn_y, btn_w, btn_h)
            # Store a special sentinel dict so the main loop knows this is "Next"
            active_buttons.append((rect, {"__action__": "next"}))
            btn_color = COLOR_BUTTON_HOVER if rect.collidepoint(mouse) else COLOR_BUTTON
            draw_panel(screen, rect.x, btn_y, btn_w, btn_h, btn_color, radius=8)
            pygame.draw.rect(screen, COLOR_BORDER, rect, width=1, border_radius=8)
            label = fonts["button"].render("Next ", True, COLOR_TEXT)
            screen.blit(label, (rect.x + (btn_w - label.get_width()) // 2, btn_y + 10))

        else:
            # ── CHOICE buttons (last page only) ──
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

    # 8. Stats HUD (always on top)
    draw_stats(screen, sanity, anger, fonts["button"])

    return active_buttons


# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
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

    # ── Scene Manager ──
    def enter_scene(scene_id):
        data  = all_scenes[scene_id]
        pager = create_pager_state(data)
        bg    = create_bg_state(data)
        return data, pager, bg

    current_id             = "start"
    scene_data, pager, bg  = enter_scene(current_id)
    sanity, anger          = 100, 0
    active_buttons         = []

    # ── Main loop ──
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
                    # Space/Enter: skip typewriter, or advance to next page
                    advance_pager(pager)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                ts = pager["text_state"]

                if not ts["done"]:
                    # Text still animating — just skip it
                    skip_animation(ts)
                else:
                    for rect, choice in active_buttons:
                        if not rect.collidepoint(mouse):
                            continue

                        # ── Next button ──
                        if choice.get("__action__") == "next":
                            advance_pager(pager)
                            break

                        # ── Choice button ──
                        next_scene = choice["next"]

                        if next_scene == "__exit__":
                            pygame.quit(); sys.exit()

                        sanity += choice.get("sanity_change", 0)
                        anger  += choice.get("anger_change",  0)
                        sanity  = max(0, min(100, sanity))
                        anger   = max(0, min(100, anger))

                        if sanity <= 0 and "madness_end" in all_scenes:
                            next_scene = "madness_end"
                        elif anger >= 100 and "rage_end" in all_scenes:
                            next_scene = "rage_end"

                        current_id            = next_scene
                        scene_data, pager, bg = enter_scene(current_id)
                        break

        pager = update_pager(pager, dt)
        bg    = update_bg(bg, dt)

        active_buttons = draw_scene(
            screen, scene_data, pager, bg, fonts, mouse,
            sanity=sanity, anger=anger
        )
        pygame.display.flip()


if __name__ == "__main__":
    run_game()
