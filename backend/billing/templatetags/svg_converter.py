import base64
from cairosvg import svg2png
from django.conf import settings
from django import template

register = template.Library()

def svg_to_base64_png(svg_content, width=100, height=100, color=None):
    try:
        if color:
            svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
            svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
        
        # Convert SVG to PNG using cairosvg
        png_data = svg2png(
            bytestring=svg_content.encode('utf-8'),
            output_width=width,
            output_height=height
        )
        
        # Convert to base64
        base64_data = base64.b64encode(png_data).decode('utf-8')
        return f"data:image/png;base64,{base64_data}"
    except Exception as e:
        print(f"Error converting SVG to PNG: {e}")
        return None

@register.simple_tag
def get_phone_call_icon_base64(color=None):
    img_svg = '''<svg width="10" height="10" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/>
                    </svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_phone_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0c-6.627 0-12 5.373-12 12s5.373 12 12 12 12-5.373 12-12-5.373-12-12-12zm3.445 17.827c-3.684 1.684-9.401-9.43-5.8-11.308l1.053-.519 1.746 3.409-1.042.513c-1.095.587 1.185 5.04 2.305 4.497l1.032-.505 1.76 3.397-1.054.516z"/>
    </svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_website_icon_base64(color=None):
    img_svg = '''<svg width="24" height="24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" fill-rule="evenodd" clip-rule="evenodd"><path d="M15.246 17c-.927 3.701-2.547 6-3.246 7-.699-1-2.32-3.298-3.246-7h6.492zm7.664 0c-1.558 3.391-4.65 5.933-8.386 6.733 1.315-2.068 2.242-4.362 2.777-6.733h5.609zm-21.82 0h5.609c.539 2.386 1.47 4.678 2.777 6.733-3.736-.8-6.828-3.342-8.386-6.733zm14.55-2h-7.28c-.29-1.985-.29-4.014 0-6h7.281c.288 1.986.288 4.015-.001 6zm-9.299 0h-5.962c-.248-.958-.379-1.964-.379-3s.131-2.041.379-3h5.962c-.263 1.988-.263 4.012 0 6zm17.28 0h-5.963c.265-1.988.265-4.012.001-6h5.962c.247.959.379 1.964.379 3s-.132 2.042-.379 3zm-8.375-8h-6.492c.925-3.702 2.546-6 3.246-7 1.194 1.708 2.444 3.799 3.246 7zm-8.548-.001h-5.609c1.559-3.39 4.651-5.932 8.387-6.733-1.237 1.94-2.214 4.237-2.778 6.733zm16.212 0h-5.609c-.557-2.462-1.513-4.75-2.778-6.733 3.736.801 6.829 3.343 8.387 6.733z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_email_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" fill="currentColor" viewBox="0 0 24 24"><path d="M0 3v18h24v-18h-24zm21.518 2l-9.518 7.713-9.518-7.713h19.036zm-19.518 14v-11.817l10 8.104 10-8.104v11.817h-20z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_wrench_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_user_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_hydrant_icon_base64(color=None):
    img_svg = '''<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M12 2a5 5 0 0 0-5 5v1H5v2h2v3H5v2h2v7h10v-7h2v-2h-2v-3h2V8h-2V7a5 5 0 0 0-5-5zm0 10a2 2 0 1 1 0-4 2 2 0 0 1 0 4z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_facebook_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M22 12a10 10 0 1 0-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0 0 22 12z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_x_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M18.24 2H21l-6.51 7.44L22 22h-6.17l-4.83-6.31L5.6 22H2.82l6.96-7.96L2 2h6.32l4.37 5.78L18.24 2zm-1.08 18h1.7L7.01 3.88H5.18L17.16 20z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_instagram_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M7 3h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4zm10 2H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm-5 3.2A3.8 3.8 0 1 1 8.2 12 3.8 3.8 0 0 1 12 8.2zm0 1.6a2.2 2.2 0 1 0 2.2 2.2A2.2 2.2 0 0 0 12 9.8zM17.4 6.4a1 1 0 1 1-1 1 1 1 0 0 1 1-1z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_whatsapp_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2C6.58 2 2.15 6.4 2.15 11.83c0 1.74.46 3.44 1.34 4.94L2 22l5.39-1.41a10 10 0 0 0 4.65 1.18h.01c5.46 0 9.89-4.4 9.89-9.83C21.94 6.4 17.5 2 12.04 2zm5.76 13.92c-.24.68-1.4 1.3-1.94 1.38-.5.08-1.12.11-1.81-.11-.42-.14-.95-.31-1.64-.6-2.88-1.25-4.76-4.15-4.9-4.34-.14-.19-1.16-1.54-1.16-2.94s.73-2.08 1-2.37c.24-.28.64-.41 1.02-.41.12 0 .23 0 .33.01.3.01.44.03.64.49.24.58.82 2 .89 2.15.07.14.12.31.02.5-.09.19-.14.31-.28.48-.14.16-.29.37-.42.49-.14.14-.28.29-.12.56.16.28.72 1.19 1.55 1.93 1.07.95 1.96 1.25 2.24 1.39.28.14.44.12.6-.07.16-.19.69-.8.88-1.08.19-.28.37-.23.62-.14.26.09 1.63.77 1.91.91.28.14.46.21.53.33.07.12.07.68-.17 1.36z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_laptop_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9H4V5zm-2 12a1 1 0 0 1 1-1h18a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_water_drop_icon_base64(color=None):
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2s7 7.2 7 12a7 7 0 0 1-14 0C5 9.2 12 2 12 2zm-1.2 15.2a2.4 2.4 0 0 1-1.6-2.2c0-.3.2-.5.5-.5s.5.2.5.5a1.4 1.4 0 0 0 1.5 1.4c.3 0 .5.2.5.5s-.2.3-.4.3z"/></svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)

@register.simple_tag
def get_recycle_icon_base64(color=None):
    # 1. Comprovem si l'usuari ha pujat un fitxer SVG personalitzat a config/assets/recycle.svg
    import os
    from django.conf import settings
    svg_path = os.path.join(settings.BASE_DIR, 'config', 'assets', 'recycle.svg')
    if os.path.exists(svg_path):
        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                img_svg = f.read()
                return svg_to_base64_png(img_svg, width=100, height=100, color=color)
        except Exception as e:
            print(f"Error reading custom recycle SVG file: {e}")

    # 2. Si no hi ha cap fitxer, usem l'SVG vectorial per defecte que combina les 3 fletxes amb una fulla al mig
    # S'utilitza fill="currentColor" perquè es pugui tenyir dinàmicament
    img_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2a10 10 0 0 0-3.9 19.2l1-1.7A8 8 0 0 1 12 4a8 8 0 0 1 5.3 2L14 9h8V1l-3.3 3.3A10 10 0 0 0 12 2zm8 10a8 8 0 0 1-5.3 7.5l1 1.7A10 10 0 0 0 22 12h-2zm-12.7 1.5l-1.7-1A10 10 0 0 0 2 12h2a8 8 0 0 1 1.3 4.5zM12 20a8 8 0 0 1-5.3-2l3.3-3H2v8l3.3-3.3A10 10 0 0 0 12 22a10 10 0 0 0 3.9-.8l-1-1.7A8 8 0 0 1 12 20z"/>
        <path d="M12 7c-2.5 0-4.5 2-4.5 4.5 0 2.8 4.5 5.5 4.5 5.5s4.5-2.7 4.5-5.5C16.5 9 14.5 7 12 7zm0 6c-.8 0-1.5-.7-1.5-1.5s.7-1.5 1.5-1.5 1.5.7 1.5 1.5-.7 1.5-1.5 1.5z"/>
    </svg>'''
    return svg_to_base64_png(img_svg, width=100, height=100, color=color)


