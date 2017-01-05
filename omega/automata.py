"""Semi-symbolic automata."""
from __future__ import absolute_import
import os
import logging
from pprint import pformat
import networkx as nx


logger = logging.getLogger(__name__)


class _SystemGraph(nx.MultiDiGraph):
    """Rooted multi-digraph with consistency methods.

    The attribute `initial_nodes` must contain nodes.
    """

    def __init__(self):
        super(_SystemGraph, self).__init__()
        self.initial_nodes = set()

    def assert_consistent(self):
        """Return `True` if attributes are conformant."""
        assert self.initial_nodes.issubset(self)

    def make_consistent(self):
        """Remove from attributes elements that are not nodes.

        Call this to update attributes like `initial_nodes`
        after removing nodes from `self`.
        """
        self.initial_nodes = self.initial_nodes.intersection(self)

    def dump(self, filename='out.pdf', rankdir='LR', prog='dot'):
        """Write to file using GraphViz via `pydot`.

        @param filename: path with exrension,
            for example: `"out.pdf"`.
        @param rankdir, prog: see `pydot.Dot.write`
        """
        name, ext = os.path.splitext(filename)
        pd = self.to_pydot()
        pd.set_rankdir(rankdir)
        pd.set_splines('true')
        pd.write(filename, format=ext[1:], prog=prog)

    def to_pydot(self):
        return nx.drawing.nx_pydot.to_pydot(self)


class Automaton(_SystemGraph):
    """Alternating acceptor of (in)finite trees.

    An acceptor represents an indicator function of a set.
    The set may contain trees (unary trees are words).

    From all the possible paths in the acceptor's graph,
    some correspond to elements of the set it describes,
    but others do not belong to this set.

    In order to distinguish elements that can be generated by
    the graph, but are not contained in the set,
    two attributes are used:

      - path quantification
      - acceptance condition


    Attributes
    ==========

    Besides `initial_nodes` an [`Automaton`] has the attributes:

      - `"universal_nodes"` is a subset of nodes.
        Remaining nodes are existentially quantified.


      - `"acceptance"` that can be:

        - `"finite"`, signifying finite words or trees
        - `"Buchi"` (or `"weak Buchi"`)
        - `"coBuchi"`
        - `"generalized Buchi"`
        - `"Rabin"`
        - `"Streett"`
        - `"Muller"`
        - `"parity"`


      - `"accepting_sets"` that contains the sets of nodes defining
        the acceptance condition:

        - `set` of nodes for (weak/co-) Buchi and finite
          For co-Buchi this is the avoidance set (FG!)
        - `list` of `dict`s of `set`s of nodes for Rabin and Streett
          The keys should be: `"GF"` and `"FG!"`,
        - `list` of `set`s of nodes for Muller and generalized Buchi,
        - a 2-`tuple` of (min, max) colors for parity
          The coloring function is defined by directly annotating the nodes.

        For convenience, the above are initialized so that
        the automaton represent an empty language.
        The user is responsible for adhering to the above conventions.

        To check compliance to the above, call [`Automaton.check_sanity`].

        Deprecated: Note that by using `SubSet(automaton)` for each set,
        you can ensure consistency if more nodes are added later.
        Alternatively, write a function that checks consistency of
        each acceptance condition wrt the automaton's nodes.


      - `vars`: `dict` mapping symbols to domains.
        Each edge that has an existential node as source is
        labeled with either:
          - an valuation of `vars`, or
          - a formula over `vars`
        These define a state predicate at the target node.
        If no variables have universal quantification,
        then the automaton recognizes words.


      - `guards` defines the representation of edge labels and can be:

        - `"formula"` meaning that each edge is annotated with
          a Boolean formula as `str` or AST. (Typically a conjunction.)
        - `"enumeration"` meaning that each edge is annotated with a letter,
          as `set` or `dict` (closed world semantics).


    Remark
    ======

    In `ltl2dstar` documentation L denotes a "good" set.
    To avoid ambiguity, `dict`s with explicit modalities are used as labels.


    References
    ==========

    - Orna Kupferman and Moshe Vardi,
      "Safraless decision procedures", FOCS'05, pp.531--542
    - Def. 10.53, p.801, U{[BK08]
      <http://tulip-control.sourceforge.net/doc/bibliography.html#bk08>}
    - U{ltl2dstar<http://ltl2dstar.de/>} documentation


    See also
    ========

    `TransitionSystem`, `Transducer`
    """

    def __init__(self, acceptance='Buchi', dvars=None,
                 universal_nodes=None, guards='bool'):
        super(Automaton, self).__init__()
        if universal_nodes is None:
            universal_nodes = set()
        # init attributes
        self.universal_nodes = universal_nodes
        self.acceptance = acceptance
        self.accepting_sets = self._init_accepting_sets(acceptance)
        self.vars = dvars
        # explicit is better than implicit
        self.guards = guards

    def __str__(self):
        show_node_data = (self.acceptance == 'parity')
        is_unary = (not self.directions or len(self.directions) <= 1)

        def f(x): return pformat(x, indent=3)
        s = (
            '{hl}\n Alternating {self.acceptance} {word_tree} automaton\n'
            '{hl}\n'
            'Alphabet:\n'
            '{self.alphabet}\n\n'
            'Directions:\n'
            '{self.directions}\n\n'
            'Nodes:\n'
            '{nodes}\n\n'
            'Initial nodes:\n'
            '{init_nodes}\n\n'
            'Universal nodes:\n'
            '{universal_nodes}\n\n'
            'Existential nodes: the rest\n\n'
            'Accepting sets:\n'
            '{accepting_sets}\n\n'
            'Edges with guards:\n'
            '{edges}\n{hl}\n').format(
                hl=40 * '-',
                self=self,
                word_tree='word' if is_unary else 'tree',
                nodes=f(self.nodes(data=show_node_data)),
                init_nodes=f(self.initial_nodes),
                universal_nodes=f(self.universal_nodes),
                accepting_sets=f(self.accepting_sets),
                edges=f(self.edges(data=True)))
        return s

    def to_pydot(self):
        # TODO: initial nodes
        g = nx.MultiDiGraph()
        for u, d in self.nodes_iter(data=True):
            if u in self.universal_nodes:
                shape = 'box'
            else:
                shape = 'circle'
            if self.acceptance in {'finite', 'Buchi', 'coBuchi'}:
                peripheries = 2
            else:
                peripheries = 1
            g.add_node(u, shape=shape, peripheries=peripheries)
        for u, v, d in self.edges_iter(data=True):
            label = ', '.join(
                '{k} = {v}'.format(k=k, v=v)
                for k, v in d.items()
                if k in self.directions or k in self.alphabet)
            g.add_edge(u, v, label=label)
        return nx.drawing.nx_pydot.to_pydot(g)

    def _init_accepting_sets(self, acceptance):
        """Return a `set`, `list` or other, depending on acceptance type."""
        if acceptance in {'finite', 'Buchi', 'coBuchi', 'weak Buchi'}:
            a = set()
        elif acceptance in {'Muller', 'generalized Buchi', 'Rabin', 'Streett'}:
            a = list()
        elif acceptance == 'parity':
            a = (None, None)
        else:
            raise ValueError('unknown acceptance: {s}'.format(s=acceptance))
        return a

    def assert_consistent(self):
        """Return `True` if conformant to conventions."""
        super(Automaton, self).asert_consistent()
        a = self.acceptance
        s = self.accepting_sets

        def f(x): return all(u in self for u in x)
        if a in {'finite', 'Buchi', 'coBuchi', 'weak Buchi'}:
            assert f(s)
        elif a in {'Muller', 'generalized Buchi'}:
            for x in s:
                assert f(s)
        elif a in {'Rabin', 'Streett'}:
            for x in s:
                assert len(x) == 2
                assert set(x) == {'[]<>', '<>[]!'}
                assert f(x['[]<>'])
                assert f(x['<>[]!'])
        elif a == 'parity':
            assert len(s) == 2
        else:
            raise Exception('Unknown acceptance: {a}'.format(a=a))
        for u, v, d in self.edges_iter(data=True):
            t = self.alphabet
            r = self.directions
            if u in self.universal_nodes:
                t, r = r, t
            for k, v in d.items():
                if k in t:
                    _check_value(v, t[k])
                assert k not in r
        return True


class TransitionSystem(_SystemGraph):
    """Enumerated or semi-symbolic transition system.

    Attributes:

      - `owner`: who selects the next node
        `in ("env", "sys")`
      - `vars`: a `dict` that maps each variable to a domain
      - `env_vars`: universally quantified variables.


    Node and edge labels
    ====================

    A node or edge attribute can be:
      - an assignment of a value to a variable, or
      - a formula as `str` (key: `"formula"`)

    These are over:
      - unprimed `vars` for nodes
      - primed and unprimed `vars` for edges

    The variable name is a key from `vars` (possibly primed).
    An assignment is interpreted as the corresponding conjunction.
    So a partial assignment is understood using open world semantics.
    """

    def __init__(self):
        super(TransitionSystem, self).__init__()
        self.owner = 'sys'
        self.vars = dict()
        self.env_vars = set()

    def __str__(self):
        return (
            '{hl}\n'
            'Transition system:\n'
            '{hl}\n'
            'Owner:\n'
            '{self.owner}\n'
            'Variables:\n'
            '{self.vars}\n'
            'Environment variables:\n'
            '{self.env_vars}\n'
            'Nodes with assignments to vars:\n'
            '{nodes}\n'
            'Initial nodes:\n'
            '{self.initial_nodes}\n'
            'Edges with actions:\n'
            '{edges}\n'
            '{hl}\n').format(
                hl=40 * '-',
                self=self,
                nodes=_dumps_nodes(self),
                edges=pformat(self.edges(data=True), indent=3))

    def to_pydot(self):
        g = nx.MultiDiGraph()
        for u, d in self.nodes_iter(data=True):
            label = ', '.join(
                '{k} = {v}'.format(k=k, v=v)
                for k, v in d.items()
                if k in self.vars)
            label = '"{u}\n{label}"'.format(u=u, label=label)
            g.add_node(u, label=label, shape='box', **d)
        for u, v, d in self.edges_iter(data=True):
            f = d.get('formula')
            if f is None:
                label = '""'
            else:
                label = '"{f}"'.format(f=f)
            g.add_edge(u, v, label=label, **d)
        return nx.drawing.nx_pydot.to_pydot(g)

    def assert_consistent(self):
        """Return `True` if attributes are conformant."""
        # TODO: check type consistency of formulae
        super(TransitionSystem, self).assert_consistent()
        assert self.owner in {'env', 'sys'}
        assert set(self.env_vars).issubset(self.vars)
        for u, d in self.nodes_iter(data=True):
            for k, v in d.items():
                if k in self.vars:
                    _check_value(v, self.vars[k])
        for u, v, d in self.edges_iter(data=True):
            for k, v in d.items():
                # primed ?
                if k.endswith("'"):
                    var = k[:-1]
                else:
                    var = k
                if var in self.vars:
                    _check_value(v, self.vars[var])
        return True


def _dumps_nodes(g):
    """Return string of graph `g` nodes."""
    r = list()
    for u, d in g.nodes_iter(data=True):
        s = '\t Node: {u}, {values}\n'.format(
            u=u,
            values=', '.join(
                '{k} = {v}'.format(k=k, v=v)
                for k, v in d.items()))
        r.append(s)
    return ''.join(r)


def _check_value(v, dom):
    """Assert that value `v` is in domain `dom`."""
    if dom == 'bool':
        assert v in (0, 1, False, True)
    elif isinstance(dom, tuple):
        assert dom[0] <= v <= dom[1]
    else:
        raise TypeError('unknown domain "{dom}"'.format(dom=dom))
