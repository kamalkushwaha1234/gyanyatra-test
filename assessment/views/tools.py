from django.shortcuts import render


def m4a_to_mp3_tool(request):
    response = render(request, "tools.html")
    response["Cross-Origin-Opener-Policy"] = "same-origin"
    response["Cross-Origin-Embedder-Policy"] = "require-corp"
    return response
