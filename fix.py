with open('main.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Yanlış yerləşən close_app tool-u sil
bad = """,{
        "name": "close_app",
        "description": "Windows-da aciq olan uygulamayi baglar. bagla, kapat, close dediginde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Baglanacak uygulama adi"
                }
            },
            "required": ["app_name"]
        }
    }"""

c = c.replace(bad, "")
print("OK: kohne close_app silindi")

# Dogru yerə əlavə et — open_app-dan sonra
close_tool = """,
    {
        "name": "close_app",
        "description": "Windows-da aciq olan uygulamayi baglar. bagla, kapat, close dediginde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Baglanacak uygulama adi"
                }
            },
            "required": ["app_name"]
        }
    }"""

target = """            "required": ["app_name"]
        }
    },
    {
        "name": "sys_info"""

replacement = """            "required": ["app_name"]
        }
    }""" + close_tool + """,
    {
        "name": "sys_info"""

c = c.replace(target, replacement)
print("OK: close_app dogru yerə elave edildi")

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(c)

print("Tamamlandi! python main.py ile ishlet.")