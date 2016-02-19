#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import time
from BeautifulSoup import BeautifulSoup
import bcrypt
import concurrent.futures
import markdown
import os.path
import re
import psycopg2
import psycopg2.extras
import tornado.escape
from tornado import gen
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

dsn = 'dbname=%s user=%s password=%s host=%s port=%s' % (
    'blog', 'blog', 'blog', '127.0.0.1', 5432)

# A thread pool to be used for password hashing with bcrypt.
executor = concurrent.futures.ThreadPoolExecutor(2)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/archive", ArchiveHandler),
            (r"/feed", FeedHandler),
            (r"/entry/([^/]+)", EntryHandler),
            (r"/compose", ComposeHandler),
            (r"/auth/create", AuthCreateHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
        ]
        settings = dict(
            blog_title=u"Tornado Blog",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            ui_modules={"Entry": EntryModule},
            xsrf_cookies=True,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/auth/login",
            debug=True,
        )
        super(Application, self).__init__(handlers, **settings)
        # Have one global connection to the blog DB across all handlers
        try:
            self.db_con = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.NamedTupleCursor)
            self.db_cur = self.db_con.cursor()
        except psycopg2.DatabaseError, e:
          print 'Error: %s' % e
          exit()


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db_cur
    def db_con(self):
        return self.application.db_con

    def get_current_user(self):
        user_id = self.get_secure_cookie("blogdemo_user")
        if not user_id: return None
        self.db.execute("SELECT * FROM authors WHERE id = %s", [int(user_id)])
        result = self.db.fetchone()
        return result

    def any_author_exists(self):
        self.db.execute("SELECT * FROM authors LIMIT 1")
        return bool(self.db.fetchall())


class HomeHandler(BaseHandler):
    def get(self):
        page = int(self.get_argument("p",0))
        topicId = self.get_argument("tId",None)
        tag = self.get_argument("t",None)
        if page > 0:
            page -= 1
        else:
            page = 0
        limit = 12
        sql = ''
        param = []

        if topicId:
            sql = ''.join([sql,'WHERE topicid = (%s) '])
            param.append(int(topicId))

        if tag:
            self.db.execute("SELECT slug FROM tags WHERE tag = %s",[tag])
            result = self.db.fetchall()
            if result == None:
                raise tornado.web.HTTPError(404)
            tagRelatedSlug = []
            for tagItem in result:
                tagRelatedSlug.append(tagItem.slug)
            print tagRelatedSlug
            sql = ''.join([sql,'WHERE slug in %s '])
            param.append(tuple(tagRelatedSlug))

        sql = ''.join(["SELECT * FROM entries ",sql,"ORDER BY published DESC LIMIT (%s) OFFSET (%s)"])
        print sql
        param.extend([limit,limit*page])
        print param
        self.db.execute(sql,param)
        # if topicId:
        #     self.db.execute("SELECT * FROM entries WHERE topicid = (%s) ORDER BY published DESC "
        #                         "LIMIT (%s) OFFSET (%s)",(topicId,limit,limit*page))
        # else:
        #     self.db.execute("SELECT * FROM entries ORDER BY published DESC "
        #                         "LIMIT (%s) OFFSET (%s)",(limit,limit*page))
        entries = self.db.fetchall()
        if not entries:raise tornado.web.HTTPError(404)
        self.render("home.html", entries=entries)


class EntryHandler(BaseHandler):
    def get(self, slug):
        self.db.execute("SELECT * FROM entries WHERE slug = %s" ,[slug])
        entry = self.db.fetchone()
        if not entry: raise tornado.web.HTTPError(404)
        self.render("entry.html", entry=entry)


class ArchiveHandler(BaseHandler):
    def get(self):
        self.db.execute("SELECT * FROM entries ORDER BY published DESC;")
        entries = self.db.fetchall()
        self.render("archive.html", entries=entries)


class FeedHandler(BaseHandler):
    def get(self):
        self.db.execute("SELECT * FROM entries ORDER BY published "
                                "DESC LIMIT 10")
        entries = self.db.fetchall()
        self.set_header("Content-Type", "application/atom+xml")
        self.render("feed.xml", entries=entries)


class ComposeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        id = self.get_argument("id", None)
        entry = None
        if id:
            self.db.execute("SELECT * FROM entries WHERE id = %s", [int(id)])
            entry = self.db.fetchone()
        self.render("compose.html", entry=entry)

    @tornado.web.authenticated
    def post(self):
        id = self.get_argument("id", None)
        title = self.get_argument("title")
        text = self.get_argument("markdown")
        link = self.get_argument("link")
        thumbnail = self.get_argument("thumbnail")
        topicId = self.get_argument("topicId")
        tags = self.get_argument("tags")
        html = markdown.markdown(text)
        excerpt = (''.join(BeautifulSoup(html).findAll(text=True)))[:64]

        if id:
            self.db.execute("SELECT * FROM entries WHERE id = %s", [int(id)])
            entry = self.db.fetchone()
            slug = entry.slug
            if not entry: raise tornado.web.HTTPError(404)
            if tags:
                if entry.tags and tags != entry.tags:
                    self.db.execute("DELETE FROM tags WHERE slug = %s", [entry.slug])
                    tags = tags.strip()
                    if ',' in tags:
                        taglist = tags.split(',')
                    else:
                        taglist = [tags]
                    for tag in taglist:
                        self.db.execute('INSERT INTO tags (slug,tag) VALUES (%s,%s)',(entry.slug,tag))
                        self.db_con().commit()

            self.db.execute(
                "UPDATE entries SET title = (%s), markdown = (%s), html = (%s), updated = now() at time zone 'utc',excerpt = (%s),thumbnail = (%s),tags = (%s) "
                "WHERE id = (%s)", (title, text, html, excerpt, thumbnail,tags,int(id)))
            self.db_con().commit()
        else:
            # slug = title.encode('unicode_escape')
            # slug = re.sub(r"[^\w]+"+'u', " ", slug)
            # slug = "-".join(slug.lower().strip().split())
            # if not slug: slug = "entry"
            slug = re.sub('\.',"-",str(time.time()))
            if tags:
                tags = tags.strip()
                if ',' in tags:
                    taglist = tags.split(',')
                else:
                    taglist = [tags]
                for tag in taglist:
                    self.db.execute('INSERT INTO tags (slug,tag) VALUES (%s,%s)',(slug,tag))
                    self.db_con().commit()
            # while True:
            #     self.db.execute("SELECT * FROM entries WHERE slug = %s",[slug])
            #     e = self.db.fetchone()
            #     if not e: break
            #     slug += "-2"
            self.db.execute(
                "INSERT INTO entries (link,thumbnail,excerpt,topicId,author_id,title,slug,markdown,html,tags,published,"
                "updated) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now() at time zone 'utc',now() at time zone 'utc')",
                (link,thumbnail,excerpt,topicId,self.current_user.id, title, slug, text, html,tags))
            self.db_con().commit()
        self.redirect("/entry/" + slug)


class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_author.html")

    @gen.coroutine
    def post(self):
        if self.any_author_exists():
            raise tornado.web.HTTPError(400, "author already created")
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            bcrypt.gensalt())
        level = 0
        credits = 0
        self.db.execute(
            "INSERT INTO authors (level, credits, email, name, hashed_password) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (int(level),int(credits),self.get_argument("email"), self.get_argument("name"),hashed_password))
        self.db_con().commit()
        author_id = self.db.fetchone()[0]
        self.set_secure_cookie("blogdemo_user", str(author_id))
        self.redirect(self.get_argument("next", "/"))


class AuthLoginHandler(BaseHandler):
    def get(self):
        # If there are no authors, redirect to the account creation page.
        if not self.any_author_exists():
            self.redirect("/auth/create")
        else:
            self.render("login.html", error=None)

    @gen.coroutine
    def post(self):
        self.db.execute("SELECT * FROM authors WHERE email = %s",[str(self.get_argument("email"))])
        author = self.db.fetchone()
        if not author:
            self.render("login.html", error="email not found")
            return
        # print author['hashed_password']
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            tornado.escape.utf8(author.hashed_password))
        if hashed_password == author.hashed_password:
            self.set_secure_cookie("blogdemo_user", str(author.id))
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="incorrect password")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("blogdemo_user")
        self.redirect(self.get_argument("next", "/"))


class EntryModule(tornado.web.UIModule):
    def render(self, entry):
        return self.render_string("modules/entry.html", entry=entry)


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(8888)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
