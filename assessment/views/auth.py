import logging
from django.contrib import messages
from django.shortcuts import render,redirect
from django.contrib.auth import authenticate,login,logout
from assessment.forms import SignUpForm,LoginForm
logger = logging.getLogger('django')

def user_signup(request):
    if not request.user.is_authenticated:
        if request.method == "POST":
            form = SignUpForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Account created successfully')
                return redirect('signin')
        else:
            form = SignUpForm()
        return render(request, 'auth.html', {'form':form,"page_title":"Sign Up"})
    else:
        messages.warning(request,"You are already logged in")
        return redirect("assessment_list")

def user_login(request):
    if not request.user.is_authenticated:
        if request.method == "POST":
            form = LoginForm(request=request,data=request.POST)
            if form.is_valid():
                email = form.cleaned_data['username']
                upass = form.cleaned_data['password']
                user = authenticate(username=email,password=upass)
                if user is not None:
                    login(request,user)
                    messages.success(request,"Logged in Successfully")
                    return redirect("assessment_list")
                else:
                    messages.error(request,"User doesn't exist")
                    return redirect("signin")
            else:
                messages.error(request,"User doesn't exist")
                return redirect("signin")    
        else:
            form = LoginForm()
            return render(request, 'auth.html',{'form':form,"page_title":"Sign In"})
    else:
        messages.warning(request,"You are already logged in")
        return redirect("assessment_list")

def user_logout(request):
    logout(request)
    messages.success(request,"Logged out Successfully")
    return redirect("signin")