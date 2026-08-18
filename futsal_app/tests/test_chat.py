from games.models import ChatMessage

from .base import BaseTestCase


class ChatMessagesViewTests(BaseTestCase):

    def test_requires_login(self):
        response = self.client.get("/games/chat/messages/")
        self.assertEqual(response.status_code, 302)

    def test_returns_last_messages_when_no_since_id(self):
        self.client.force_login(self.user_1_per)
        ChatMessage.objects.create(user=self.user_1_per, message="hello")
        ChatMessage.objects.create(user=self.user_2_per, message="hi there")

        response = self.client.get("/games/chat/messages/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["message"], "hello")
        self.assertEqual(data["messages"][0]["author"], "bolek")
        self.assertTrue(data["messages"][0]["is_own"])
        self.assertFalse(data["messages"][1]["is_own"])

    def test_returns_only_messages_since_given_id(self):
        self.client.force_login(self.user_1_per)
        first = ChatMessage.objects.create(user=self.user_1_per, message="first")
        ChatMessage.objects.create(user=self.user_1_per, message="second")

        response = self.client.get(f"/games/chat/messages/?since_id={first.id}")

        data = response.json()
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["message"], "second")


class ChatSendViewTests(BaseTestCase):

    def test_requires_login(self):
        response = self.client.post("/games/chat/send/", {"message": "hello"})
        self.assertEqual(response.status_code, 302)

    def test_creates_message_for_logged_in_user(self):
        self.client.force_login(self.user_1_per)
        response = self.client.post("/games/chat/send/", {"message": "hello team"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "hello team")
        self.assertEqual(data["author"], "bolek")
        self.assertTrue(data["is_own"])
        self.assertEqual(ChatMessage.objects.count(), 1)

    def test_rejects_empty_message(self):
        self.client.force_login(self.user_1_per)
        response = self.client.post("/games/chat/send/", {"message": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_get_not_allowed(self):
        self.client.force_login(self.user_1_per)
        response = self.client.get("/games/chat/send/")

        self.assertEqual(response.status_code, 405)
