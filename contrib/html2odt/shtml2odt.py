#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2008 Søren Roug, European Environment Agency
#
# This is free software.  You may redistribute it under the terms
# of the Apache license and the GNU General Public License Version
# 2 or at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Contributor(s):
#
#
import string, sys, re
import urllib2, htmlentitydefs, urlparse
from urllib import quote_plus
from HTMLParser import HTMLParser
from cgi import escape,parse_header
from types import StringType

from odf.opendocument import OpenDocumentText
from odf import dc, text, table
import htmlstyles


def checkurl(url, http_proxy=None):
    """ grab and convert url
    """
    url = string.strip(url)
#   if url.lower()[:5] != "http:":
#       raise IOError, "Only http is accepted"

    if http_proxy:
        _proxies = { 'http': http_proxy }
    else:
        _proxies = {}
    proxy_support = urllib2.ProxyHandler(_proxies)
    opener = urllib2.build_opener(proxy_support, urllib2.HTTPHandler)

    urllib2.install_opener(opener)

    req = urllib2.Request(url)
    req.add_header("User-agent", "HTML2ODT: Convert HTML to OpenDocument")
    conn = urllib2.urlopen(req)

    if not conn:
        raise IOError, "Failure in open"
    data = conn.read()
    headers = conn.info()
    conn.close()

    encoding = 'iso8859-1'  #Standard HTML
    if headers.has_key('content-type'):
        (ct, parms) = parse_header(headers['content-type'])
        if parms.has_key('charset'):
            encoding = parms['charset']

    mhp = HTML2ODTParser(encoding, url)
    failure = ""
    mhp.feed(data)
    return  mhp

entityref = re.compile('&([a-zA-Z][-.a-zA-Z0-9]*)[^a-zA-Z0-9]')
charref = re.compile('&#(?:[0-9]+|[xX][0-9a-fA-F]+)[^0-9a-fA-F]')
incomplete = re.compile('&[a-zA-Z#]')
ampersand = re.compile('&')

def listget(list, key, default=None):
    for l in list:
        if l[0] == key:
            default = l[1]
    return default

class TagObject:

    def __init__(self, tag, attrs, output_loc):
        self.tag = tag
        self.attrs = attrs
        self.output_loc = output_loc

class HTML2ODTParser(HTMLParser):

    def __init__(self, encoding, baseurl):
        HTMLParser.__init__(self)
        self.doc = OpenDocumentText()
        self.curr = self.doc.text
        htmlstyles.addStandardStyles(self.doc)
        self.encoding = encoding
        (scheme, host, path, params, fragment) = urlparse.urlsplit(baseurl)
        lastslash = path.rfind('/')
        if lastslash > -1:
            path = path[:lastslash]
        self.baseurl = urlparse.urlunsplit((scheme, host, path,'',''))
        self.basehost = urlparse.urlunsplit((scheme, host, '','',''))
        self.sectnum = 0
        self.tagstack = []
        self.pstack = []
        self.processelem = True
        self.processcont = True
        self.__data = []
        self.elements = {
     'a':    (self.s_html_a, self.close_tag),
     'base': ( self.output_base, None),
     'b':    ( self.s_html_emphasis, self.close_tag),
     'br':   ( self.output_br, None),
     'col':  ( self.s_html_col, None),
     'dd':   ( self.s_html_dd, self.close_tag),
     'dt':   ( self.s_html_dt, None),
     'div':  ( self.s_html_section, self.e_html_section),
     'em':   ( self.s_html_emphasis, self.close_tag),
     'h1':   ( self.s_html_headline, self.close_tag),
     'h2':   ( self.s_html_headline, self.close_tag),
     'h3':   ( self.s_html_headline, self.close_tag),
     'h4':   ( self.s_html_headline, self.close_tag),
     'h5':   ( self.s_html_headline, self.close_tag),
     'h6':   ( self.s_html_headline, self.close_tag),
     'head': ( self.s_ignorexml, None),
     'i':    ( self.s_html_emphasis, self.close_tag),
     'img':  ( self.output_img, None),
     'li':   ( self.s_html_li, self.e_html_li),
     'meta': ( self.meta_encoding, None),
     'ol':   ( self.output_ol, self.e_html_list),
     'p':    ( self.s_html_block, self.e_html_block),
     'span': ( self.s_html_span, self.close_tag),
     'strong':( self.s_html_emphasis, self.close_tag),
     'table':( self.s_html_table, self.e_html_table),
     'td':   ( self.s_html_td, self.close_tag),
     'th':   ( self.s_html_td, self.close_tag),
     'title':( self.s_html_title, self.e_html_title),
     'tr':   ( self.s_html_tr, self.close_tag),
     'ul':   ( self.output_ul, self.e_html_list),
     'var':  ( self.s_html_emphasis, self.close_tag),
     'input':( self.output_input, None),
     'select':( self.output_select, None),
     'textarea':( self.output_textarea, None),
    }


    def result(self):
        """ Return a string
            String must be in UNICODE
        """
        str = string.join(self.__data,'')
        self.__data = []
        return str

    def meta_name(self, attrs):
        """ Look in meta tag for textual info"""
        foundit = 0
        # Is there a name attribute?
        for attr in attrs:
            if attr[0] == 'name' and string.lower(attr[1]) in ('description',
            'keywords','title',
            'dc.description','dc.keywords','dc.title'
            ):
                foundit = 1
        if foundit == 0:
            return 0

        # Is there a content attribute?
        content = self.find_attr(attrs,'content')
        if content:
            self.handle_data(u' ')
            self.handle_attr(content)
            self.handle_data(u' ')
        return 1

    def meta_encoding(self, tag, attrs):
        """ Look in meta tag for page encoding (Content-Type)"""
        foundit = 0
        # Is there a content-type attribute?
        for attr in attrs:
            if attr[0] == 'http-equiv' and string.lower(attr[1]) == 'content-type':
                foundit = 1
        if foundit == 0:
            return 0

        # Is there a content attribute?
        for attr in attrs:
            if attr[0] == 'content':
                (ct, parms) = parse_header(attr[1])
                if parms.has_key('charset'):
                    self.encoding = parms['charset']
        return 1

    def s_ignorexml(self, tag, attrs):
        self.processelem = False

    def output_base(self, tag, attrs):
        """ Change the document base if there is a base tag """
        baseurl = listget(attrs, 'href', self.baseurl)
        (scheme, host, path, params, fragment) = urlparse.urlsplit(baseurl)
        lastslash = path.rfind('/')
        if lastslash > -1:
            path = path[:lastslash]
        self.baseurl = urlparse.urlunsplit((scheme, host, path,'',''))
        self.basehost = urlparse.urlunsplit((scheme, host, '','',''))

    def output_br(self, tag, attrs):
        self.curr.addElement(text.LineBreak())

    def s_html_emphasis(self, tag, attrs):
        tagdict = {
           'b': 'Bold',
           'em':'Emphasis',
           'i':'Italic',
           'strong': 'Strong_20_Emphasis',
           'var':'Variable'}
        e = text.Span(stylename=tagdict.get(tag,'Emphasis'))
        self.curr.addElement(e)
        self.curr = e

    def s_html_span(self, tag, attrs):
        e = text.Span()
        self.curr.addElement(e)
        self.curr = e

    def s_html_title(self, tag, attrs):
        e = dc.Title()
        self.doc.meta.addElement(e)
        self.curr = e

    def e_html_title(self, tag):
        self.curr = self.curr.parentNode

    def output_img(self, tag, attrs):
        src = listget(attrs, 'src', "Illegal IMG tag!")
        alt = listget(attrs, 'alt', src)
        # Must remember name of image and download it.
        self.write_odt(u'<draw:image xlink:href="Pictures/%s" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>' % '00000.png')

    def s_html_a(self, tag, attrs):
        href = None
        href = listget(attrs, 'href', None)
        if href:
            if href in ("", "#"):
                href == self.baseurl
            elif href.find("://") >= 0:
                pass
            elif href[0] == '/':
                href = self.basehost + href
            e = text.A(type="simple", href=href)
        else:
            e = text.A()
#       if self.curr.parentNode.qname != text.P().qname:
#           p = text.P()
#           self.curr.addElement(p)
#           self.curr = p
        self.curr.addElement(e)
        self.curr = e

    def close_tag(self, tag):
        self.curr = self.curr.parentNode

    def s_html_dd(self, tag, attrs):
        e = text.P(stylename="List_20_Contents")
        self.curr.addElement(e)
        self.curr = e

    def s_html_dt(self, tag, attrs):
        self.write_odt(u'<text:p text:style-name="List_20_Heading">')

    def output_ul(self, tag, attrs):
        self.write_odt(u'<text:list text:style-name="List_20_1">')

    def output_ol(self, tag, attrs):
        self.write_odt(u'<text:list text:style-name="Numbering_20_1">')

    def e_html_list(self, tag):
        self.write_odt(u'</text:list>')

    def s_html_li(self, tag, attrs):
        self.write_odt(u'<text:list-item><text:p text:style-name="P1">')

    def e_html_li(self, tag):
        self.write_odt(u'</text:p></text:list-item>')

    def output_select(self, tag, attrs):
        return
        self.write_odt(u'<br/>Combo box:')

    def output_textarea(self, tag, attrs):
        return
        self.write_odt(u'<form:textarea>')

    def output_input(self, tag, attrs):
        return
        type = listget(attrs, 'type', "text")
        value = listget(attrs, 'value', "")
        if type == "text":
            self.write_odt(u'<br/>Edit:')
        elif type == "submit":
            self.write_odt(u' %s' % value)
        elif type == "checkbox":
            #FIXME - Only works in XHTML
            checked = listget(attrs, 'checked', "not checked")
            self.write_odt(u'<br/>Checkbox:' % checked)
        elif type == "radio":
            checked = listget(attrs, 'checked', "not checked")
            self.write_odt(u'<br/>Radio button:' % checked)
        elif type == "file":
            self.write_odt(u'File upload edit %s' % value)
            self.write_odt(u'<br/>Browse button:')

    def s_html_headline(self, tag, attrs):
        self.write_odt(u'<text:h text:style-name="Heading_20_%s" text:outline-level="%s">' % (tag[1],tag[1]))
        e = text.H(stylename="Heading_20_%s" % tag[1], outlinelevel=tag[1])
        self.curr.addElement(e)
        self.curr = e

    def s_html_table(self, tag, attrs):
        e = table.Table()
        self.curr.addElement(e)
        self.curr = e

    def e_html_table(self, tag):
        self.curr = self.curr.parentNode

    def s_html_td(self, tag, attrs):
        e = table.TableCell()
        self.curr.addElement(e)
        self.curr = e

    def s_html_tr(self, tag, attrs):
        e = table.TableRow()
        self.curr.addElement(e)
        self.curr = e

    def s_html_col(self, tag, attrs):
        e = table.TableColumn()
        self.curr.addElement(e)

    def s_html_section(self, tag, attrs):
        """ Outputs block tag such as <p> and <div> """
        name = self.find_attr(attrs,'id')
        if name is None:
            self.sectnum = self.sectnum + 1
            name = "Sect%d" % self.sectnum
        e = text.Section(name=name)
        self.curr.addElement(e)
        self.curr = e

    def e_html_section(self, tag):
        """ Outputs block tag such as <p> and <div> """
        self.curr = self.curr.parentNode

    def s_html_block(self, tag, attrs):
        """ Outputs block tag such as <p> and <div> """
        e = text.P(stylename="Text_20_body")
        self.curr.addElement(e)
        self.curr = e

    def e_html_block(self, tag):
        """ Outputs block tag such as <p> and <div> """
        self.curr = self.curr.parentNode
#
# HANDLE STARTTAG
#
    def handle_starttag(self, tag, attrs):
        self.pstack.append( (self.processelem, self.processcont) )
        tagobj = TagObject(tag, attrs, self.last_data_pos())
        self.tagstack.append(tagobj)

        method = self.elements.get(tag, (None, None))[0]
        if self.processelem and method:
            method(tag, attrs)
#
# HANDLE END
#
    def handle_endtag(self, tag):
        """ 
        """
        tagobj = self.tagstack.pop()
        method = self.elements.get(tag, (None, None))[1]
        if self.processelem and method:
            method(tag)
        self.processelem, self.processcont = self.pstack.pop()


#
# Data operations
#
    def handle_data(self, data):
        if data.strip() == '': return
        if self.processelem and self.processcont:
            self.curr.addText(data)

    def write_odt(self, data):
        """ Collect the data to show on the webpage """
        if type(data) == StringType:
            data = unicode(data, self.encoding)
        self.__data.append(data)

    def last_data_pos(self):
        return len(self.__data)

    def find_attr(self, attrs, key):
        """ Run through the attibutes to find a specific one
            return None if not found
        """
        for attr in attrs:
            if attr[0] == key:
                return attr[1]
        return None

#
# Tagstack operations
#
    def find_tag(self, tag):
        """ Run down the stack to find the last entry with the same tag name
            Not Tested
        """
        for tagitem in range(len(self.tagstack), 0, -1):
            if tagitem.tag == tag:
                return tagitem
        return None

    def handle_charref(self, name):
        """ Handle character reference for UNICODE
        """
        if name[0] in ('x', 'X'):
            try:
                n = int(name[1:],16)
            except ValueError:
                return
        else:
            try:
                n = int(name)
            except ValueError:
                return
        if not 0 <= n <= 65535:
            return
        self.handle_data(unichr(n))

    def handle_entityref(self, name):
        """Handle entity references.
        """
        table = htmlentitydefs.name2codepoint
        if name in table:
            self.handle_data(unichr(table[name]))
        else:
            return

    def handle_attr(self, attrval):
        """ Scan attribute values for entities and resolve them
            Simply calls handle_data
        """
        i = 0
        n = len(attrval)
        while i < n:
            match = ampersand.search(attrval, i) #
            if match:
                j = match.start()
            else:
                j = n
            if i < j: self.handle_data(attrval[i:j])
            i = j
            if i == n: break
            startswith = attrval.startswith
            if startswith('&#', i):
                match = charref.match(attrval, i)
                if match:
                    name = match.group()[2:-1]
                    self.handle_charref(name)
                    k = match.end()
                    if not startswith(';', k-1):
                        k = k - 1
                    i = k
                    continue
                else:
                    break
            elif startswith('&', i):
                match = entityref.match(attrval, i)
                if match:
                    name = match.group(1)
                    self.handle_entityref(name)
                    k = match.end()
                    if not startswith(';', k-1):
                        k = k - 1
                    i = k
                    continue
                match = incomplete.match(attrval, i)
                if match:
                    # match.group() will contain at least 2 chars
                    if match.group() == attrval[i:]:
                        self.error("EOF in middle of entity or char ref")
                    # incomplete
                    break
                elif (i + 1) < n:
                    # not the end of the buffer, and can't be confused
                    # with some other construct
                    self.handle_data("&")
                    i = i + 1
                else:
                    break
            else:
                assert 0, "interesting.search() lied"
        # end while
        if i < n:
            self.handle_data(attrval[i:n])
            i = n

if __name__ == "__main__":
    import sys
    result = checkurl(sys.argv[1])
    print result.doc.xml()
    result.doc.save("helloworld", True)


