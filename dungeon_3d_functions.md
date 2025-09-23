# Documentation technique des fonctions et classes du fichier dungeon_3d.py

## Classes

### Dungeon
- **__init__(self, width=20, height=20)** : Initialise la grille du donjon et la liste des salles.
- **_room_overlaps(self, new_room, existing_rooms)** : Vérifie si une nouvelle salle chevauche une salle existante.
- **_create_room(self, room)** : Place une salle sur la grille.
- **_create_corridor(self, x1, y1, x2, y2)** : Crée un couloir horizontal/vertical entre deux points.
- **generate_rooms(self, max_rooms=10, min_size=3, max_size=6)** : Génère des salles aléatoires sans chevauchement.
- **generate_corridors(self)** : Relie les salles par des couloirs.
- **generate(self)** : Génère l’ensemble du donjon (salles + couloirs).
- **is_wall(self, x, y)** : Vérifie si une position est un mur ou hors limites.

### Player3D
- **__init__(self, x, y)** : Initialise la position, les points de vie, l’angle, le champ de vision, etc.
- **move(self, dx, dy, dungeon)** : Déplace le joueur si la case n’est pas un mur.
- **rotate(self, angle_delta)** : Modifie l’angle de vue du joueur.
- **take_damage(self, damage)** : Applique des dégâts au joueur.
- **update(self)** : Met à jour les cooldowns de tir et de flash.
- **use_potion(self, potion_use_sound=None)** : Utilise une potion pour soigner le joueur.
- **_calculate_shoot_angle(self, mouse_x, screen_width)** : Calcule l’angle de tir selon la position de la souris.
- **_play_shoot_sound(self)** : Joue le son du tir.
- **shoot(self, mouse_x, mouse_y, screen_width, screen_height, enemies, dungeon)** : Crée un projectile selon la position de la souris.

### Bullet
- **__init__(self, x, y, angle, is_player_bullet=True, z=1.0, z_velocity=0.0)** : Initialise la position, l’angle, la vitesse, la durée de vie, etc.
- **update(self, dungeon)** : Déplace le projectile et vérifie les collisions.

### HealthPotion
- **__init__(self, x, y)** : Initialise la position et la quantité de soin de la potion.

### Enemy
- **__init__(self, x, y, enemy_type=None, available_types=None)** : Initialise la position, le type, les timers et les animations de l’ennemi.
- **_try_move_random(self, dungeon)** : Déplacement aléatoire de l’ennemi.
- **_try_move(self, dungeon, player, enemies)** : Déplacement intelligent vers le joueur (pathfinding).
- **_try_shoot(self, player)** : Tente de tirer sur le joueur si à portée.
- **_update_animations(self)** : Met à jour les animations de tir et de coup reçu.
- **update(self, player, dungeon, enemies)** : Met à jour l’ennemi (déplacement, tir, animation).

### Game
- **__init__(self)** : Initialise le jeu, la fenêtre, les ressources et les entités.
- **setup_dungeon(self)** : Crée et génère le donjon.
- **is_valid_potion_position(self, x, y)** : Vérifie si une position est valide pour une potion.
- **is_near_wall(self, x, y, min_distance=2)** : Vérifie si une position est trop proche d’un mur.
- **place_potions(self, num_potions=6, max_attempts=50)** : Place les potions dans le donjon.
- **place_entities(self)** : Place le joueur, les ennemis et les potions dans le donjon.
- **handle_input(self, keys)** : Gère les entrées clavier pour le joueur.
- **update_bullets(self)** : Met à jour les projectiles et gère les collisions.
- **collect_potions(self)** : Gère la collecte des potions par le joueur.
- **show_instructions(self)** : Affiche l’écran d’instructions.
- **show_end_screen(self, message, color, enemies_killed, elapsed_time)** : Affiche l’écran de fin de partie.
- **render_entity(self, enemy, width, height)** : Affiche un ennemi en perspective 3D.
- **render_potion(self, potion, width, height)** : Affiche une potion en perspective 3D.
- **render_bullet(self, bullet, width, height)** : Affiche un projectile en perspective 3D.
- **render_walls(self, width, height)** : Affiche les murs du donjon en 3D.
- **render_player_ui(self, width, height)** : Affiche l’interface du joueur (barre de vie, viseur, potions, etc.).
- **render_3d(self)** : Affiche la scène 3D complète (murs, entités, UI).
- **draw_minimap(self)** : Affiche la mini-carte du donjon.
- **run(self)** : Boucle principale du jeu.

## Fonctions utilitaires
- **get_all_enemy_sprites()** : Charge et retourne les sprites d’ennemis (cache).
- **get_enemy_sprite(enemy_type="orc")** : Retourne le sprite d’un type d’ennemi.
- **get_available_enemy_types()** : Retourne la liste des types d’ennemis disponibles.
- **generate_enemy_sprite(enemy_type="orc")** : Génère un sprite d’ennemi par dessin.
- **render_sprite(screen, sprite, x, y, distance, screen_height)** : Affiche un sprite avec la bonne perspective.
- **cast_ray(player, angle, dungeon, max_distance=20, step=0.1)** : Simule un rayon pour détecter la distance à un mur.
- **has_line_of_sight(player, enemy, dungeon)** : Vérifie la visibilité entre le joueur et un ennemi.
- **find_path(dungeon, start, goal)** : Algorithme A* pour le pathfinding.
- **get_perspective_params(obj_x, obj_y, player, width, height)** : Calcule la distance, l’angle relatif et la position à l’écran pour le rendu 3D.

---
Chaque fonction et méthode est décrite brièvement pour faciliter la compréhension et la maintenance du code.
