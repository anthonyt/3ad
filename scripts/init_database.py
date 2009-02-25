if __name__ == "__main__":
	import sys
	import os

	# ensure the main ad3 module is on the path
	parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	if parent_dir not in sys.path:
		sys.path.append(parent_dir)

	from ad3.model import AudioFile, Plugin
	from ad3.controller import db, controller

	# drop the old tables
	db.dropTables();

	# create the fresh tables
	db.createTables();

	# Create an audio file object for each file in the listings file
	# (Also dynamically create tags to represent each tag in the file)
	files = [
		(u"audio/Cello note a.wav", u"cello strings"),
		(u"audio/Cello note c.wav", u"cello strings"),
		(u"audio/Cello note g.wav", u"cello strings"),
		(u"audio/Baritone saxophone C major scale ascending descend_BLASTWAVEFX_27547.wav", u"saxophone"),
		(u"audio/Beat musical acoustic guitar progression loop 01_SFXBible_ss00381.wav", u"guitar"),
		(u"audio/banjo.wav", u""),
		(u"audio/drums.wav", u"noise drums"),
		(u"audio/happy-wind-bed-100b.wav", u"wind"),
		(u"audio/_01 Eine Kleine Nachtmusik I_ Allegro.m4a.wav", u""),
		(u"audio/_01 Jeux.m4a.wav", u"orchestra"),
		(u"audio/_01 Night of Silence.m4a.wav", u"piano"),
		(u"audio/_02 Aries' Theme.m4a.wav", u"piano"),
		(u"audio/_02 Eine Kleine Nachtmusik II_ Romanze (Andante).m4a.wav", u"orchestra strings"),
		(u"audio/_03 Eine Kleine Nachtmusik III_ Menuett (Allegretto).m4a.wav", u"orchestra strings"),
		(u"audio/_04 Eine Kleine Nachtmusik IV_ Rondo (Allegro).m4a.wav", u"orchestra strings"),
		(u"audio/_05 Allemanda - Partita No. 6 in E minor.m4a.wav", u"piano"),
		(u"audio/_05 Legebit.m4a.wav", u"piano"),
		(u"audio/_06 Fugue.m4a.wav", u"harpsichord"),
		(u"audio/_06 Sonata in A Major D664.wav", u"piano"),
		(u"audio/_06 To Zanarkand.m4a.wav", u"piano"),
		(u"audio/_07 Eyes On Me.m4a.wav", u"piano"),
		(u"audio/_08 Theme to Voyager.m4a.wav", u"piano"),
		(u"audio/_09 Sonata in A Major D664.wav", u"piano"),
		(u"audio/_12 Terra's Theme.m4a.wav", u"piano"),
		(u"audio/_15 Concerto No. 11 - Allegro - Adagio spiccato e tutti - Allegro.m4a.wav", u"strings"),
		(u"audio/_16 Concerto No. 11 - Largo e spiccato.m4a.wav", u"strings"),
		(u"audio/_17 Concerto No. 11 - Allegro.m4a.wav", u"strings"),
		(u"audio/_19 Clouds.wav", u"debussy"),
		(u"audio/_2-18 Symphony No. 88 in G - I.m4a.wav", u"orchestra"),
		(u"audio/_2-19 Symphony No. 88 in G - I.m4a.wav", u"orchestra"),
		(u"audio/_2-20 Symphony No. 88 in G - I.m4a.wav", u"orchestra"),
		(u"audio/_2-21 Symphony No. 88 in G - I.m4a.wav", u"orchestra"),
		(u"audio/_2-22 Symphony No. 88 in G - I.m4a.wav", u"orchestra"),
		(u"audio/_2-23 Symphony No. 88 in G - I.m4a.wav", u"orchestra"),
		(u"audio/_2-24 Symphony No. 88 in G - II.m4a.wav", u"orchestra"),
		(u"audio/_2-24 Symphony No. 95 In C Minor.wav", u"strings"),
		(u"audio/_2-25 Symphony No. 88 in G - II.m4a.wav", u""),
		(u"audio/_2-25 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_2-26 Symphony No. 88 in G - II.m4a.wav", u""),
		(u"audio/_2-26 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_2-27 Symphony No. 88 in G - II.m4a.wav", u""),
		(u"audio/_2-27 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_2-28 Symphony No. 88 in G - III.m4a.wav", u""),
		(u"audio/_2-28 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_2-29 Symphony No. 88 in G - III.m4a.wav", u""),
		(u"audio/_2-30 Symphony No. 88 in G - III.m4a.wav", u""),
		(u"audio/_2-31 Symphony No. 88 in G - III.m4a.wav", u""),
		(u"audio/_2-32 Symphony No. 88 in G - IV.m4a.wav", u"strings orchestra"),
		(u"audio/_2-32 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_2-33 Symphony No. 88 in G - IV.m4a.wav", u""),
		(u"audio/_2-33 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_2-34 Symphony No. 88 in G - IV.m4a.wav", u""),
		(u"audio/_2-34 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_2-35 Symphony No. 88 in G - IV.m4a.wav", u""),
		(u"audio/_2-35 Symphony No. 95 In C Minor.wav", u""),
		(u"audio/_20 Clouds.wav", u"debussy"),
		(u"audio/_21 Clouds.wav", u""),
		(u"audio/_22 Clouds.wav", u""),
		(u"audio/_23 Clouds.wav", u"debussy"),
		(u"audio/_24 Clouds.wav", u"debussy")]
	for (fname, tagstring) in files:
		controller.add_file(fname, tagstring)

	# Set up the default plugins
	plugins = [
		('charlotte', 'ad3.plugins.charlotte'),
		#('bextract', 'ad3.plugins.bextract_plugin'),
		#('centroid', 'ad3.plugins.centroid_plugin')
	]

	# Save all plugins that aren't already in the database.
	for plugin in plugins:
		controller.add_plugin(plugin[0], plugin[1])


	# Finally, print out the data that we just entered.
	for file in db.query(AudioFile):
		print file, file.tags
	for plugin in db.query(Plugin):
		print plugin
