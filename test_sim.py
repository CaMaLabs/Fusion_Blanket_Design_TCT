import openmc

# Material
mat = openmc.Material(name='tungsten')
mat.add_element('W', 1.0)
mat.set_density('g/cm3', 19.3)

materials = openmc.Materials([mat])
materials.export_to_xml()

# Geometry: 5 cm tungsten slab
surf1 = openmc.XPlane(x0=0.0, boundary_type='vacuum')
surf2 = openmc.XPlane(x0=5.0, boundary_type='vacuum')

cell = openmc.Cell(fill=mat, region=+surf1 & -surf2)
geom = openmc.Geometry([cell])
geom.export_to_xml()

# Source: 14 MeV neutron slightly inside the slab
source = openmc.IndependentSource()
source.space = openmc.stats.Point((0.1, 0.0, 0.0))
source.angle = openmc.stats.Isotropic()
source.energy = openmc.stats.Discrete([14.0e6], [1.0])

# Settings: FIXED SOURCE, not eigenvalue
settings = openmc.Settings()
settings.run_mode = 'fixed source'
settings.source = source
settings.batches = 50
settings.particles = 50000
settings.export_to_xml()
