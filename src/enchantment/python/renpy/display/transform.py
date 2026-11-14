"""Transforms. An ATL transform is the ATL tree already in the bundle, named
by the node of the statement that defined it, plus its parameters and the
values bound to them (REWORK-PLAN §6.3); the C ATL VM runs it."""
from renpy import missing_attribute


class ATLTransform:
    def __init__(self, atl, child=None, context={}, parameters=None, **properties):
        self.atl = atl  # the node index of the `image`/`transform` statement
        self.child = child
        self.context = context
        self.parameters = parameters  # the harvested signature, or None
        self.properties = properties

    def _show(self):
        # Ren'Py computes the transform's starting state here; that's the
        # ATL VM's, when the transform is shown.
        pass


def __getattr__(name):
    return missing_attribute("renpy.display.transform", name)
