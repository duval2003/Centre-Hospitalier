from .models import ChatMessage


def chat_notifications(request):
    if not request.user.is_authenticated:
        return {'unread_chat_count': 0}

    return {
        'unread_chat_count': ChatMessage.objects.filter(
            receiver=request.user,
            is_read=False,
        ).count(),
    }