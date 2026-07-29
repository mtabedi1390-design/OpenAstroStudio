"""
examples/example_astropy_coords.py
------------------------------------
اثبات مفهوم کامل: Reflection -> Graph -> Code Generation -> Execution
با استفاده از astropy واقعی، بدون نیاز به GUI.

اجرا:
    python3 -m astrostudio.examples.example_astropy_coords
"""

from astropy.coordinates import SkyCoord

from astrostudio.engine.reflection import reflect
from astrostudio.engine.graph import Graph
from astrostudio.engine.node import NodeInstance
from astrostudio.engine.codegen import generate_code
from astrostudio.engine.executor import execute_direct
from astrostudio.engine.overrides import skycoord_node_spec

from astrostudio.libraries.astropy_adapters import to_galactic, separation_deg


def main():
    print("=" * 60)
    print("۱) Reflection: SkyCoord (override دستی) و to_galactic (خودکار)")
    print("=" * 60)

    # SkyCoord امضای واقعی‌اش را پشت **kwargs مخفی می‌کند -> از override دستی
    # استفاده می‌کنیم (توضیح کامل در engine/overrides.py).
    skycoord_spec = skycoord_node_spec()
    galactic_spec = reflect(to_galactic, category="astropy.coordinates",
                             display_name="To Galactic")

    print(f"- {skycoord_spec.display_name}: {[p.name for p in skycoord_spec.params]}")
    print(f"- {galactic_spec.display_name}: {[p.name for p in galactic_spec.params]}")
    print(f"  توضیح: {galactic_spec.description}")
    print()

    print("=" * 60)
    print("۲) ساخت گراف: Coordinate --> To Galactic")
    print("=" * 60)

    graph = Graph()

    coord_node = NodeInstance.create(skycoord_spec, position=(0, 0))
    coord_node.param_values.update({"ra": 10.68, "dec": 41.27, "unit": "deg"})
    graph.add_node(coord_node)

    galactic_node = NodeInstance.create(galactic_spec, position=(250, 0))
    graph.add_node(galactic_node)

    graph.connect(coord_node.id, "result", galactic_node.id, "coord")

    print(f"تعداد Node: {len(graph.nodes)} | تعداد Connection: {len(graph.connections)}")
    print()

    print("=" * 60)
    print("۳) کد پایتون تولیدشده (اصل شفافیت)")
    print("=" * 60)
    print(generate_code(graph))
    print()

    print("=" * 60)
    print("۴) اجرای واقعی گراف")
    print("=" * 60)
    result = execute_direct(graph)
    if result.success:
        galactic_coord = result.results[galactic_node.id]
        print(f"موفق. خروجی Node نهایی (Galactic): {galactic_coord}")
        print(f"  l = {galactic_coord.l:.4f}   b = {galactic_coord.b:.4f}")
    else:
        print(f"خطا در اجرا: {result.error}")

    print()
    print("=" * 60)
    print("۵) تست دوم: separation_deg با دو ورودی از دو Node مستقل")
    print("=" * 60)

    graph2 = Graph()
    c1 = NodeInstance.create(skycoord_node_spec(), position=(0, 0))
    c1.param_values.update({"ra": 10.68, "dec": 41.27, "unit": "deg"})
    c2 = NodeInstance.create(skycoord_node_spec(), position=(0, 150))
    c2.param_values.update({"ra": 15.0, "dec": 41.0, "unit": "deg"})

    sep_spec = reflect(separation_deg, category="astropy.coordinates")
    sep_node = NodeInstance.create(sep_spec, position=(250, 75))

    graph2.add_node(c1)
    graph2.add_node(c2)
    graph2.add_node(sep_node)
    graph2.connect(c1.id, "result", sep_node.id, "coord1")
    graph2.connect(c2.id, "result", sep_node.id, "coord2")

    result2 = execute_direct(graph2)
    if result2.success:
        print(f"فاصله‌ی زاویه‌ای: {result2.results[sep_node.id]:.4f} درجه")
    else:
        print(f"خطا: {result2.error}")


if __name__ == "__main__":
    main()
