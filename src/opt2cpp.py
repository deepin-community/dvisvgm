##########################################################################
## opt2cpp.py                                                           ##
##                                                                      ##
## This file is part of dvisvgm - a fast DVI to SVG converter           ##
## Copyright (C) 2016-2021 Martin Gieseking <martin.gieseking@uos.de>   ##
## and Khaled Hosny <khaled.hosny@hindawi.com>                          ##
##                                                                      ##
## This program is free software; you can redistribute it and/or        ##
## modify it under the terms of the GNU General Public License as       ##
## published by the Free Software Foundation; either version 3 of       ##
## the License, or (at your option) any later version.                  ##
##                                                                      ##
## This program is distributed in the hope that it will be useful, but  ##
## WITHOUT ANY WARRANTY; without even the implied warranty of           ##
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the         ##
## GNU General Public License for more details.                         ##
##                                                                      ##
## You should have received a copy of the GNU General Public License    ##
## along with this program; if not, see <http://www.gnu.org/licenses/>. ##
##########################################################################

from lxml import etree
import re
import sys

hpp_template = """// This file was automatically generated by opt2cpp.
// It is part of the dvisvgm package and published under the terms
// of the GNU General Public License version 3, or (at your option) any later version.
// See file COPYING for further details.
// Copyright (C) 2016-2021 Martin Gieseking <martin.gieseking@uos.de>

#ifndef {guard}
#define {guard}

#include <config.h>
#include <array>
#include <vector>
#include "CLCommandLine.hpp"

using CL::Option;
using CL::TypedOption;

class {class} : public CL::CommandLine {{
\tpublic:
\t\t{class} () : CL::CommandLine(
\t\t\t"{summary}",
\t\t\t"{usage}",
\t\t\t"{copyright}"
\t\t) {{}}

\t\t{class} (int argc, char **argv) : CommandLine() {{
\t\t\tparse(argc, argv);
\t\t}}

\t\t// option variables
{optvars}
\tprotected:
\t\tstd::vector<OptSectPair>& options () const override {{return _options;}}
\t\tconst char* section (size_t n) const override {{return n < _sections.size() ? _sections[n] : nullptr;}}

\tprivate:
\t\t{sectarray}
\t\tmutable {optvec}}};

#endif
"""

def create_hpp (optfile):
    parser = etree.XMLParser(dtd_validation=True)
    tree = etree.parse(optfile, parser=parser)
    root = tree.getroot()

    vars = {}
    vars["class"] = root.get("class")
    vars["guard"] = "{}_HPP".format(vars["class"].upper())

    prog = root.xpath("/*/program")[0]
    vars["summary"] = prog.findtext("description")
    vars["copyright"] = prog.findtext("copyright")
    vars["usage"] = ""
    for usage in prog.xpath("usage"):
        vars["usage"] += "{}\\n".format(usage.text)
    vars["usage"] = vars["usage"][:-2]

    sections = root.xpath("//section")
    vars["sectarray"] = "std::array<const char*, {}> _sections {{{{\n".format(len(sections))
    for sect in sections:
        vars["sectarray"] += '\t\t\t"{}",\n'.format(sect.get("title"))
    vars["sectarray"] += "\t\t}};\n"

    vars["optvars"] = ""
    options = root.xpath("//option")
    for optelem in sorted(options, key=lambda opt: opt.get("long")):
        check_redefinition(optelem)
        vars["optvars"] += "\t\t{}\n".format(create_optvar(optelem))

    vars["optvec"] = "std::vector<OptSectPair> _options = {\n"
    for optelem in options:
        sectnum = int(optelem.xpath("count(../preceding-sibling::section)"))
        vecentry = '\t\t\t{{&{}, {}}},'.format(create_optname(optelem), sectnum)
        if (optelem.get("if")):
            vecentry = "#if {}\n{}\n#endif".format(optelem.get("if"), vecentry)
        vars["optvec"] += "{}\n".format(vecentry)
    vars["optvec"] += "\t\t};\n";

    return hpp_template.format(**vars)

# Check if a short option name is already in use.
# It's not necessary to check the long option names because they are IDs handled by the validator.
def check_redefinition (optelem):
    shortname = optelem.get("short")
    count = optelem.xpath('count(preceding::option[@short="%s"])' % shortname)
    assert count == 0, "redefinition of option -%s" % shortname

# Returns the C++ variable definition of an option including its initializer list.
def create_optvar (optelem):
    typename = "Option"
    argelem = optelem.find("arg")
    if argelem is not None:
        argtype = argelem.get("type")
        argname = argelem.get("name")
        argval  = argelem.get("default")
        if argtype == "string":
            argtype = "std::string"
        argmode = "OPTIONAL" if optelem.xpath("arg/@optional='yes'") else "REQUIRED"
        typename = "TypedOption<%s, Option::ArgMode::%s>" %(argtype, argmode)
    longname = optelem.get("long")
    shortname = optelem.get("short") if optelem.get("short") else "\\0"
    descr = optelem.xpath("description/text()")[0]
    if argelem is not None:
        if argval is None:
            return '{} {} {{"{}", \'{}\', "{}", "{}"}};'.format(typename, create_optname(optelem), longname, shortname, argname, descr)
        if argtype == "std::string":
            argval = '"{}"'.format(argval)
        return '{} {} {{"{}", \'{}\', "{}", {}, "{}"}};'.format(typename, create_optname(optelem), longname, shortname, argname, argval, descr)
    return '{} {} {{"{}", \'{}\', "{}"}};'.format(typename, create_optname(optelem), longname, shortname, descr)

# Returns the C++ variable name of an option.
def create_optname (optelem):
    optname = "%sOpt" % optelem.get("long")
    return re.sub('-([a-z])', lambda pat: pat.group(1).upper(), optname)

if __name__ == "__main__":
    print(create_hpp(sys.argv[1]))

