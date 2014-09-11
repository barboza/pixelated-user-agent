#
# Copyright (c) 2014 ThoughtWorks, Inc.
#
# Pixelated is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pixelated is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Pixelated. If not, see <http://www.gnu.org/licenses/>.
from pixelated.adapter.status import Status
from pixelated.support.id_gen import gen_pixelated_uid
import pixelated.support.date
import dateutil.parser as dateparser
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText


class PixelatedMail:

    def __init__(self):
        pass

    @staticmethod
    def from_leap_mail(leap_mail, leap_mail_collection=None):
        mail = PixelatedMail()
        mail.leap_mail = leap_mail
        mail.leap_mail._collection = leap_mail_collection  # Work around until they fix the issue of mails not having the collection set on a LeapMailbox
        mail.body = leap_mail.bdoc.content['raw']
        mail.headers = mail._extract_headers()
        mail.date = PixelatedMail._get_date(mail.headers)
        mail.ident = gen_pixelated_uid(leap_mail._mbox, leap_mail.getUID())
        mail.status = set(mail._extract_status())
        mail.security_casing = {}
        mail.tags = mail._extract_tags()
        return mail

    def set_from(self, _from):
        self.headers['from'] = [_from]

    def get_to(self):
        return self.headers['to']

    def get_cc(self):
        return self.headers['cc']

    def get_bcc(self):
        return self.headers['bcc']

    def _extract_status(self):
        return Status.from_flags(self.leap_mail.getFlags())

    def _split_recipients(self, header_type, temporary_headers):
        if(temporary_headers.get(header_type) is not None):
            recipients = temporary_headers[header_type].split(',')
            temporary_headers[header_type] = map(lambda x: x.lstrip(), recipients)

    def _extract_headers(self):
        temporary_headers = {}
        for header, value in self.leap_mail.hdoc.content['headers'].items():
            temporary_headers[header.lower()] = value

        map(lambda x: self._split_recipients(x, temporary_headers), ['to', 'bcc', 'cc'])

        return temporary_headers

    def _extract_tags(self):
        return set(self.headers.get('x-tags', []))

    def update_tags(self, tags):
        old_tags = self.tags
        self.tags = tags
        removed = old_tags.difference(tags)
        added = tags.difference(old_tags)
        self._persist_mail_tags(tags)
        return added, removed

    def mark_as_read(self):
        self.leap_mail.setFlags((Status.PixelatedStatus.SEEN,), 1)
        self.status = self._extract_status()
        return self

    def _persist_mail_tags(self, current_tags):
        hdoc = self.leap_mail.hdoc
        hdoc.content['headers']['X-Tags'] = list(current_tags)
        self.leap_mail._soledad.put_doc(hdoc)

    def has_tag(self, tag):
        return tag in self.tags

    def as_dict(self):
        statuses = [status.name for status in self.status]
        _headers = self.headers.copy()
        _headers['date'] = self.date
        return {
            'header': _headers,
            'ident': self.ident,
            'tags': list(self.tags),
            'status': statuses,
            'security_casing': self.security_casing,
            'body': self.body
        }

    def to_mime_multipart(self):
        mime_multipart = MIMEMultipart()
        mime_multipart['To'] = ", ".join(self.headers['to'])
        mime_multipart['Cc'] = ", ".join(self.headers['cc'])
        mime_multipart['Bcc'] = ", ".join(self.headers['bcc'])
        mime_multipart['Subject'] = self.headers['subject']
        mime_multipart['Date'] = self.headers['date']
        mime_multipart.attach(MIMEText(self.body, 'plain'))
        return mime_multipart

    def to_smtp_format(self, _from=None):
        mime_multipart = self.to_mime_multipart()
        mime_multipart['From'] = _from
        return mime_multipart.as_string()

    @staticmethod
    def from_dict(mail_dict):
        return from_dict(mail_dict)

    @classmethod
    def _get_date(cls, headers):
        date = headers.get('date', None)
        if not date:
            date = headers['received'].split(";")[-1].strip()
        return dateparser.parse(date).isoformat()


def from_dict(mail_dict):
    mail = PixelatedMail()
    mail.headers = mail_dict.get('header', {})
    mail.headers['date'] = pixelated.support.date.iso_now()
    mail.body = mail_dict.get('body', '')
    mail.ident = mail_dict.get('ident', None)
    mail.tags = set(mail_dict.get('tags', []))
    mail.status = set(mail_dict.get('status', []))
    return mail
