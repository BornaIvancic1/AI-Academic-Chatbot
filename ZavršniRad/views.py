import time

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI

from . import settings
from .models import Student, Profesor, Admin, ChatMessage, ChatSession

User = get_user_model()
def is_admin(user):
    return hasattr(user, 'admin')
def is_not_admin(user):
    return not is_admin(user)
@never_cache
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            if hasattr(user, 'admin'):
                return redirect('createUser')
            else:
                return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'index.html')
def remove_source(answer):
    start_index = answer.find('【')
    end_index = answer.find('】')
    if start_index != -1 and end_index != -1:
        answer = answer[:start_index] + answer[end_index + 1:]
    else:
        return "My capabilities to provide an answer are limited in this context."
    return answer.strip()

@login_required
@user_passes_test(is_not_admin)
def home_view(request):
    if request.method == 'GET':
        chat_sessions = ChatSession.objects.filter(user=request.user).order_by('-start_time')
        return render(request, 'home.html', {'chat_sessions': chat_sessions})

    elif request.method == 'POST':
        bot_response = None
        error_message = None

        user_input = request.POST.get('user_input')
        user = request.user

        if not user_input:
            error_message = 'Please enter your question.'
        else:
            try:
                ASSISTANT_ID = settings.ASSISTANT_ID
                client = OpenAI(api_key=settings.OPENAI_API_KEY)

                thread = client.beta.threads.create(
                    messages=[{"role": "user", "content": user_input}]
                )

                run = client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=ASSISTANT_ID
                )

                while run.status != "completed":
                    run = client.beta.threads.runs.retrieve(
                        thread_id=thread.id, run_id=run.id
                    )
                    time.sleep(1)

                messages = client.beta.threads.messages.list(thread_id=thread.id)
                latest_message = messages.data[0]
                bot_clean = latest_message.content[0].text.value
                bot_response = remove_source(bot_clean)

                now = timezone.now()
                chat_session = ChatSession.objects.filter(user=user, start_time__lte=now).last()

                if not chat_session or (now - chat_session.start_time).total_seconds() > 3600:
                    chat_session = ChatSession.objects.create(user=user)

                ChatMessage.objects.create(chat_session=chat_session, user_message=user_input, bot_response=bot_response)

            except Exception as e:
                error_message = f"An error occurred: {e}"

        return JsonResponse({
            'bot_response': bot_response,
            'error': error_message
        })

@user_passes_test(is_admin)
@login_required
def createUser_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        user_type = request.POST.get('user_type')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already in use.')
            return redirect('createUser')

        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=make_password(password)
        )

        if user_type == 'student':
            Student.objects.create(user=user)
        elif user_type == 'professor':
            Profesor.objects.create(user=user)
        elif user_type == 'admin':
            Admin.objects.create(user=user)

        messages.success(request, 'User created successfully.')
        return redirect('createUser')

    return render(request, 'createUser.html')

def upload_file(file):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.files.create(file=file, purpose='answers')
    return response['id']

def delete_file_from_openai(file_id):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    client.files.delete(file_id=file_id)

@user_passes_test(is_admin)
@login_required
def modification_view(request):
    context = {}
    assistant_id = settings.ASSISTANT_ID
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    if request.method == 'POST':
        new_files = request.FILES.getlist('add_files')
        new_file_ids = []

        for f in new_files:
            try:
                file_id = upload_file(f)
                new_file_ids.append(file_id)
            except Exception as e:
                context['message'] = f'Error uploading file: {str(e)}'
                return render(request, 'modification.html', context)

        delete_files = request.POST.getlist('delete_files')

        for file_id in delete_files:
            try:
                delete_file_from_openai(file_id)
            except Exception as e:
                context['message'] = f'Error deleting file: {str(e)}'
                return render(request, 'modification.html', context)

        updated_instructions = request.POST.get('instructions')

        try:
            assistant = client.beta.assistants.retrieve(assistant_id=assistant_id)
            file_ids = [file['id'] for file in assistant['files']]
        except Exception as e:
            context['message'] = f'Error retrieving assistant files: {str(e)}'
            return render(request, 'modification.html', context)

        updated_file_ids = [f for f in file_ids + new_file_ids if f not in delete_files]

        try:
            client.beta.assistants.update(
                assistant_id=assistant_id,
                instructions=updated_instructions,
                files=updated_file_ids
            )
        except Exception as e:
            context['message'] = f'Error updating assistant: {str(e)}'
            return render(request, 'modification.html', context)

        context['message'] = 'Assistant successfully updated.'
        return redirect(reverse('modification'))

    else:
        try:
            assistant = client.beta.assistants.retrieve(assistant_id=assistant_id)
            context['assistant'] = assistant
        except Exception as e:
            context['message'] = f'Error retrieving assistant: {str(e)}'
            return render(request, 'modification.html', context)

    return render(request, 'modification.html', context)

@login_required
def me_view(request):
    user_type = request.user.get_user_type()
    context = {
        'user_type': user_type,
    }
    return render(request, 'me.html', context)

def chat_session_detail(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    messages = session.messages.all()
    return render(request, 'chatSessionDetail.html', {'session': session, 'messages': messages})