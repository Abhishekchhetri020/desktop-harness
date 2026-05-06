"""Mail.app adapter — draft / read / search; sending requires explicit confirm."""
from __future__ import annotations

from typing import Optional

from .base import Adapter


def _escape_as(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


class MailAdapter(Adapter):
    name = "Mail"
    bundle_ids = ("com.apple.mail",)
    app_class = "applescript"
    safe_actions = (
        "draft_email", "list_inbox", "search_mail", "read_selected_email",
        "list_mailboxes",
    )
    dangerous_actions = (
        "send_email",  # sending == external action; never auto.
    )

    # ----- safe / drafting only -----

    def do_draft_email(
        self,
        to: str | list[str],
        subject: str,
        body: str = "",
        cc: Optional[str | list[str]] = None,
        bcc: Optional[str | list[str]] = None,
    ) -> dict:
        """Open a new compose window with fields pre-filled. Does NOT send."""
        from ..applescript import osascript
        from ..apps import activate

        def _join(addrs):
            if addrs is None: return None
            if isinstance(addrs, str): return addrs
            return ", ".join(addrs)

        to_s = _join(to) or ""
        cc_s = _join(cc)
        bcc_s = _join(bcc)
        script_lines = [
            'tell application "Mail"',
            'set newMessage to make new outgoing message with properties {{visible:true, subject:"{subject}", content:"{body}"}}'.format(
                subject=_escape_as(subject), body=_escape_as(body)
            ),
            'tell newMessage',
        ]
        for addr in (to_s.split(",") if to_s else []):
            a = addr.strip()
            if a:
                script_lines.append(
                    f'make new to recipient at end of to recipients with properties {{address:"{_escape_as(a)}"}}'
                )
        if cc_s:
            for addr in cc_s.split(","):
                a = addr.strip()
                if a:
                    script_lines.append(
                        f'make new cc recipient at end of cc recipients with properties {{address:"{_escape_as(a)}"}}'
                    )
        if bcc_s:
            for addr in bcc_s.split(","):
                a = addr.strip()
                if a:
                    script_lines.append(
                        f'make new bcc recipient at end of bcc recipients with properties {{address:"{_escape_as(a)}"}}'
                    )
        script_lines += ['end tell', 'activate', 'end tell']
        try:
            osascript("\n".join(script_lines))
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "hint": "Grant Automation permission for Mail."}
        try: activate("Mail")
        except Exception: pass
        return {"ok": True, "action": "draft_email", "to": to_s, "subject": subject,
                "note": "Draft window opened. Review and click Send manually, "
                        "or call send_email(..., confirm=True) to send programmatically."}

    def do_list_inbox(self, limit: int = 20) -> dict:
        from ..applescript import osascript
        try:
            out = osascript(
                'tell application "Mail"\n'
                '  set out to ""\n'
                '  set theMessages to messages of inbox\n'
                f'  set N to (count of theMessages)\n'
                f'  if N > {limit} then set N to {limit}\n'
                '  repeat with i from 1 to N\n'
                '    set m to item i of theMessages\n'
                '    set out to out & subject of m & " || " & sender of m & linefeed\n'
                '  end repeat\n'
                '  return out\n'
                'end tell'
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}
        rows = []
        for line in (out or "").splitlines():
            if "||" in line:
                subj, sender = line.split("||", 1)
                rows.append({"subject": subj.strip(), "from": sender.strip()})
        return {"ok": True, "action": "list_inbox", "count": len(rows), "messages": rows}

    def do_search_mail(self, query: str, limit: int = 20) -> dict:
        from ..applescript import osascript
        q = _escape_as(query)
        script = (
            'tell application "Mail"\n'
            f'  set theMessages to (messages of inbox whose subject contains "{q}")\n'
            '  set out to ""\n'
            f'  set N to (count of theMessages)\n'
            f'  if N > {limit} then set N to {limit}\n'
            '  repeat with i from 1 to N\n'
            '    set m to item i of theMessages\n'
            '    set out to out & subject of m & " || " & sender of m & linefeed\n'
            '  end repeat\n'
            '  return out\n'
            'end tell'
        )
        try:
            out = osascript(script)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        rows = []
        for line in (out or "").splitlines():
            if "||" in line:
                subj, sender = line.split("||", 1)
                rows.append({"subject": subj.strip(), "from": sender.strip()})
        return {"ok": True, "action": "search_mail", "query": query, "messages": rows}

    def do_read_selected_email(self) -> dict:
        from ..applescript import osascript
        try:
            subject = osascript('tell application "Mail" to get subject of (item 1 of (selection as list))')
            sender = osascript('tell application "Mail" to get sender of (item 1 of (selection as list))')
            content = osascript('tell application "Mail" to get content of (item 1 of (selection as list))')
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "hint": "Mail must be frontmost with a message selected."}
        return {"ok": True, "action": "read_selected_email",
                "subject": (subject or "").strip(),
                "from": (sender or "").strip(),
                "body": content or ""}

    def do_list_mailboxes(self) -> dict:
        from ..applescript import osascript
        try:
            out = osascript(
                'tell application "Mail"\n'
                '  set out to ""\n'
                '  repeat with mb in mailboxes\n'
                '    set out to out & name of mb & linefeed\n'
                '  end repeat\n'
                '  return out\n'
                'end tell'
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "action": "list_mailboxes",
                "mailboxes": [n for n in (out or "").splitlines() if n.strip()]}

    # ----- DANGEROUS: actually send -----

    def do_send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        *,
        cc: Optional[str | list[str]] = None,
        bcc: Optional[str | list[str]] = None,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> dict:
        """Send an email programmatically. ALWAYS requires confirm=True OR dry_run=True."""
        from ..safety import confirmed_action

        def _send():
            from ..applescript import osascript

            def _join(addrs):
                if addrs is None: return None
                if isinstance(addrs, str): return addrs
                return ", ".join(addrs)

            to_s = _join(to) or ""
            cc_s = _join(cc)
            bcc_s = _join(bcc)

            script_lines = [
                'tell application "Mail"',
                'set newMessage to make new outgoing message with properties {{visible:false, subject:"{subj}", content:"{body}"}}'.format(
                    subj=_escape_as(subject), body=_escape_as(body)
                ),
                'tell newMessage',
            ]
            for addr in (to_s.split(",") if to_s else []):
                a = addr.strip()
                if a:
                    script_lines.append(
                        f'make new to recipient at end of to recipients with properties {{address:"{_escape_as(a)}"}}'
                    )
            if cc_s:
                for addr in cc_s.split(","):
                    a = addr.strip()
                    if a:
                        script_lines.append(
                            f'make new cc recipient at end of cc recipients with properties {{address:"{_escape_as(a)}"}}'
                        )
            if bcc_s:
                for addr in bcc_s.split(","):
                    a = addr.strip()
                    if a:
                        script_lines.append(
                            f'make new bcc recipient at end of bcc recipients with properties {{address:"{_escape_as(a)}"}}'
                        )
            script_lines += ['send', 'end tell', 'end tell']
            osascript("\n".join(script_lines))
            return {"to": to_s, "subject": subject, "body_chars": len(body)}

        return confirmed_action(
            "send_email", _send,
            confirm=confirm, dry_run=dry_run, target=subject, app="Mail",
        )
