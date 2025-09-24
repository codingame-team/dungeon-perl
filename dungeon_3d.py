import random
import pygame
import math
from load_assets import load_enemy_sprites, load_textures
import os
import json
import pickle
from datetime import datetime

pygame.mixer.init()

# Constantes de perspective
VERTICAL_PERSPECTIVE_FACTOR = 160  # Facteur pour la position verticale des sprites

class Dungeon:
    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        self.grid = [[0] * width for _ in range(height)]
        self.rooms = []
    
    def _room_overlaps(self, new_room, existing_rooms):
        x, y, w, h = new_room["x"], new_room["y"], new_room["w"], new_room["h"]
        return any(x < r["x"] + r["w"] and x + w > r["x"] and y < r["y"] + r["h"] and y + h > r["y"] for r in existing_rooms)
    
    def _create_room(self, room):
        for i in range(room["x"], room["x"] + room["w"]):
            for j in range(room["y"], room["y"] + room["h"]):
                self.grid[j][i] = 1
    
    def _create_corridor(self, x1, y1, x2, y2):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if self.grid[y1][x] == 0:
                self.grid[y1][x] = 1
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if self.grid[y][x2] == 0:
                self.grid[y][x2] = 1
    
    def generate_rooms(self, max_rooms=10, min_size=3, max_size=6):
        for _ in range(max_rooms):
            w, h = random.randint(min_size, max_size), random.randint(min_size, max_size)
            x, y = random.randint(1, self.width - w - 1), random.randint(1, self.height - h - 1)
            new_room = {"x": x, "y": y, "w": w, "h": h}
            
            if not self._room_overlaps(new_room, self.rooms):
                self.rooms.append(new_room)
                self._create_room(new_room)
    
    def generate_corridors(self):
        for i in range(len(self.rooms) - 1):
            a, b = self.rooms[i], self.rooms[i + 1]
            ax, ay = a["x"] + a["w"] // 2, a["y"] + a["h"] // 2
            bx, by = b["x"] + b["w"] // 2, b["y"] + b["h"] // 2
            self._create_corridor(ax, ay, bx, by)
    
    def generate(self):
        self.generate_rooms()
        self.generate_corridors()
    
    def is_wall(self, x, y):
        return (x < 0 or x >= self.width or y < 0 or y >= self.height or 
                self.grid[int(y)][int(x)] == 0)

class Player3D:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.z = 0.0  # Ground level
        self.eye_height = 2.0  # Eye height above ground
        self.angle = 0
        self.fov = math.pi / 3
        self.hp = 250
        self.max_hp = 250
        self.shoot_cooldown = 0
        self.potions = 0
        self.shoot_flash = 0
        
        # Système d'XP
        self.level = 1
        self.xp = 0
        self.xp_to_next_level = 100  # XP requis pour le niveau suivant

    def move(self, dx, dy, dungeon):
        new_x = self.x + dx * 0.1
        new_y = self.y + dy * 0.1
        
        if not dungeon.is_wall(new_x, new_y):
            self.x, self.y = new_x, new_y
    
    def rotate(self, angle_delta):
        self.angle += angle_delta
    
    def take_damage(self, damage):
        self.hp = max(0, self.hp - damage)
    
    def update(self):
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        if self.shoot_flash > 0:
            self.shoot_flash -= 1

    def use_potion(self, potion_use_sound=None):
        if self.potions > 0 and self.hp < self.max_hp:
            self.potions -= 1
            heal_amount = random.randint(20, 40)
            self.hp = min(self.max_hp, self.hp + heal_amount)
            if potion_use_sound:  # Vérifier si le son est chargé
                potion_use_sound.set_volume(0.6)
                potion_use_sound.play()
            return True
        return False
    
    def gain_xp(self, amount):
        """Ajoute de l'XP et gère la montée de niveau"""
        self.xp += amount

        # Vérifier si le joueur peut monter de niveau
        while self.xp >= self.xp_to_next_level:
            self.xp -= self.xp_to_next_level
            self.level += 1
            # Augmenter les PV max à chaque niveau
            self.max_hp += 25
            self.hp = self.max_hp  # Restaurer la santé complète lors du level up
            # Augmenter l'XP requis pour le niveau suivant (progression exponentielle)
            self.xp_to_next_level = int(self.xp_to_next_level * 1.5)

            return True  # Indique qu'un level up a eu lieu
        return False  # Pas de level up

    def get_xp_percentage(self):
        """Retourne le pourcentage d'XP actuel pour la barre"""
        return self.xp / self.xp_to_next_level if self.xp_to_next_level > 0 else 1.0

    def roll_damage(self):
        """Lance les dés de dégâts du joueur basés sur son niveau"""
        # Dégâts de base : 1d6 + niveau
        base_damage = random.randint(1, 6) + self.level
        # Bonus de dégâts tous les 3 niveaux
        bonus_dice = self.level // 3
        for _ in range(bonus_dice):
            base_damage += random.randint(1, 4)
        return base_damage

    def roll_attack(self, target_level=1):
        """Détermine si l'attaque du joueur réussit"""
        # Précision de base : 75% + 2% par niveau
        base_accuracy = 75 + (self.level * 2)

        # Malus si l'ennemi est de niveau supérieur
        level_diff = target_level - self.level
        effective_accuracy = base_accuracy - (level_diff * 5)  # -5% par niveau de différence
        effective_accuracy = max(15, min(95, effective_accuracy))  # Entre 15% et 95%

        roll = random.randint(1, 100)
        return roll <= effective_accuracy
    def _calculate_shoot_angle(self, mouse_x, screen_width):
        center_x = screen_width // 2
        angle_offset = (mouse_x - center_x) / center_x * (self.fov / 2)
        return self.angle + angle_offset
    
    def _play_shoot_sound(self):
        try:
            shoot_sound = pygame.mixer.Sound(buffer=b'\x00\x80' * 1500)
            shoot_sound.set_volume(0.8)
            shoot_sound.play()
        except:
            pass
    
    def shoot(self, mouse_x, mouse_y, screen_width, screen_height, enemies, dungeon):
        if self.shoot_cooldown > 0:
            return None
        
        shoot_angle = self._calculate_shoot_angle(mouse_x, screen_width)
        self.shoot_cooldown = 30
        self.shoot_flash = 8
        self._play_shoot_sound()
        
        # Hauteur d'épaule (un peu plus bas que les yeux)
        shoulder_height = self.eye_height - 0.2
        
        # Calculer la hauteur cible basée sur la position verticale de la souris
        center_y = screen_height // 2
        vertical_offset = (mouse_y - center_y) / center_y
        target_height = shoulder_height - vertical_offset * 2.0  # Ajuster la sensibilité
        
        # Calculer la distance approximative vers le mur/cible
        distance, _, _ = cast_ray(self, shoot_angle, dungeon)
        
        # Calculer la vélocité verticale pour atteindre la cible
        z_velocity = (target_height - shoulder_height) / (distance / 0.3) if distance > 0 else 0
        
        return Bullet(self.x, self.y, shoot_angle, True, shoulder_height, z_velocity)

class Bullet:
    def __init__(self, x, y, angle, is_player_bullet=True, z=1.0, z_velocity=0.0):
        self.x = x
        self.y = y
        self.z = z  # Height above ground
        self.angle = angle
        self.z_velocity = z_velocity  # Vertical velocity
        self.speed = 0.3
        self.life = 60
        self.is_player_bullet = is_player_bullet
    
    def update(self, dungeon):
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed
        self.z += self.z_velocity
        self.life -= 1
        
        # Hit ground or wall
        return (not dungeon.is_wall(self.x, self.y) and self.life > 0 and self.z >= 0)

class HealthPotion:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.z = 0.0  # Ground level
        self.heal_amount = random.randint(20, 40)

class Enemy:
    def __init__(self, x, y, enemy_type=None, available_types=None):
        self.x = x
        self.y = y
        self.z = 0.0  # Ground level
        self.height = 2.2  # Enemy height (plus grand que le joueur)
        self.ground_level = True  # Flag for ground-level rendering
        
        # Use available types from loaded sprites or fallback
        if available_types is None:
            available_types = ["orc", "skeleton", "goblin", "troll"]
        
        # Random enemy type if not specified
        if enemy_type is None:
            self.enemy_type = random.choice(available_types)
        else:
            self.enemy_type = enemy_type

        # Définir les statistiques selon le type d'ennemi
        self._set_stats_for_type(self.enemy_type)

        self.move_timer = 0
        self.shoot_timer = 0
        self.is_shooting = False
        self.shoot_animation = 0
        self.hit_animation = 0
        self.death_animation = 0
        self.is_dead = False

    def _set_stats_for_type(self, enemy_type):
        """Définit les statistiques selon le type d'ennemi"""
        stats = {
            "goblin": {
                "hp": 20, "max_hp": 20, "level": 1, "xp_value": 15,
                "damage_dice": (1, 4), "accuracy": 65  # 1d4 dégâts, 65% précision
            },
            "skeleton": {
                "hp": 35, "max_hp": 35, "level": 2, "xp_value": 25,
                "damage_dice": (1, 6), "accuracy": 70  # 1d6 dégâts, 70% précision
            },
            "orc": {
                "hp": 50, "max_hp": 50, "level": 3, "xp_value": 35,
                "damage_dice": (1, 8), "accuracy": 75  # 1d8 dégâts, 75% précision
            },
            "troll": {
                "hp": 80, "max_hp": 80, "level": 4, "xp_value": 50,
                "damage_dice": (2, 6), "accuracy": 80  # 2d6 dégâts, 80% précision
            }
        }

        enemy_stats = stats.get(enemy_type, stats["skeleton"])
        self.hp = enemy_stats["hp"]
        self.max_hp = enemy_stats["max_hp"]
        self.level = enemy_stats["level"]
        self.xp_value = enemy_stats["xp_value"]
        self.damage_dice = enemy_stats["damage_dice"]  # (nombre_dés, faces_par_dé)
        self.accuracy = enemy_stats["accuracy"]  # Pourcentage de précision

    def take_damage(self, damage):
        """L'ennemi prend des dégâts"""
        if self.is_dead:
            return False

        self.hp = max(0, self.hp - damage)
        self.hit_animation = 15

        if self.hp <= 0:
            self.is_dead = True
            self.death_animation = 30
            return True  # Ennemi tué
        return False  # Ennemi blessé mais vivant

    def roll_damage(self):
        """Lance les dés de dégâts pour cette attaque"""
        num_dice, dice_faces = self.damage_dice
        total_damage = 0
        for _ in range(num_dice):
            total_damage += random.randint(1, dice_faces)
        return total_damage

    def roll_attack(self, target_level=1):
        """Détermine si l'attaque réussit"""
        # Calculer la précision effective basée sur les niveaux
        level_diff = self.level - target_level
        effective_accuracy = self.accuracy + (level_diff * 5)  # +/-5% par niveau de différence
        effective_accuracy = max(10, min(95, effective_accuracy))  # Entre 10% et 95%

        roll = random.randint(1, 100)
        return roll <= effective_accuracy


    def _try_move_random(self, dungeon):
        # return  # Désactiver le mouvement des ennemis pour réduire la difficulté
        self.move_timer += 1
        if self.move_timer > 30:  # Move more frequently
            dx, dy = random.choice([-0.1, 0, 0.1]), random.choice([-0.1, 0, 0.1])  # Smaller steps
            new_x, new_y = self.x + dx, self.y + dy
            
            if not dungeon.is_wall(new_x, new_y):
                self.x, self.y = new_x, new_y
            self.move_timer = 0

    def _try_move(self, dungeon, player, enemies):
        if self.move_timer > 0:
            self.move_timer -= 1
            return

        self.move_timer = 30  # Temps entre chaque mouvement

        # Calculer le chemin vers le joueur
        start = (int(self.x), int(self.y))
        goal = (int(player.x), int(player.y))
        path = find_path(dungeon, start, goal)

        if path and len(path) > 1:
            next_step = path[1]
            new_x, new_y = next_step

            # Vérifier si la nouvelle position est dans les limites de la carte
            if 0 <= new_x < dungeon.width and 0 <= new_y < dungeon.height:
                # Vérifier si la nouvelle position n'est pas un mur
                if not dungeon.is_wall(new_x, new_y):
                    # Vérifier si la nouvelle position ne chevauche pas un autre monstre
                    if not any(math.sqrt((new_x - e.x) ** 2 + (new_y - e.y) ** 2) < 0.5 for e in enemies if e != self):
                        # Déplacement progressif pour un mouvement fluide
                        self.x += (new_x - self.x) * 0.5
                        self.y += (new_y - self.y) * 0.5

    def _try_shoot(self, player):
        distance = math.sqrt((player.x - self.x) ** 2 + (player.y - self.y) ** 2)
        if distance < 4:  # Portée actuelle
            self.shoot_timer += 1
            if self.shoot_timer > 120:
                self.is_shooting = True
                self.shoot_animation = 15
                self.shoot_timer = 0
                try:
                    shoot_sound = pygame.mixer.Sound(buffer=b'\x00\xFF' * 2000)
                    shoot_sound.set_volume(1.0)
                    shoot_sound.play()
                except:
                    pass

                angle_to_player = math.atan2(player.y - self.y, player.x - self.x)
                bullet_z = self.z + self.height / 2
                return Bullet(self.x, self.y, angle_to_player, False, bullet_z, 0.0)
        return None
    
    def _update_animations(self):
        if self.shoot_animation > 0:
            self.shoot_animation -= 1
            if self.shoot_animation == 0:
                self.is_shooting = False
        
        if self.hit_animation > 0:
            self.hit_animation -= 1

        if self.death_animation > 0:
            self.death_animation -= 1
            if self.death_animation == 0:
                # Réinitialiser l'ennemi après la mort (pour le recyclage ou autre chose)
                self.hp = 0
                self.max_hp = 0
                self.is_dead = True  # Marquer comme mort et désactiver les actions

    def update(self, player, dungeon, enemies):
        distance_to_player = math.sqrt((player.x - self.x) ** 2 + (player.y - self.y) ** 2)

        if has_line_of_sight(player, self, dungeon):
            if distance_to_player > 4:  # Distance de tir
                dx = player.x - self.x
                dy = player.y - self.y
                norm = math.sqrt(dx ** 2 + dy ** 2)
                new_x = self.x + (dx / norm) * 0.1
                new_y = self.y + (dy / norm) * 0.1

                # Vérifier collisions avec murs et ennemis
                if not dungeon.is_wall(new_x, new_y) and not any(math.sqrt((new_x - e.x) ** 2 + (new_y - e.y) ** 2) < 0.5 for e in enemies if e != self):
                    self.x, self.y = new_x, new_y
            else:
                return self._try_shoot(player)  # Tirer si à portée

        self._update_animations()
        return None


# Global sprite cache
_enemy_sprites_cache = None

def get_all_enemy_sprites():
    """Get all loaded enemy sprites (cached)"""
    global _enemy_sprites_cache
    if _enemy_sprites_cache is None:
        _enemy_sprites_cache = load_enemy_sprites()
    return _enemy_sprites_cache

def get_enemy_sprite(enemy_type="orc"):
    """Get enemy sprite from cache or generate fallback"""
    sprites = get_all_enemy_sprites()
    return sprites.get(enemy_type, generate_enemy_sprite(enemy_type))

def get_available_enemy_types():
    """Get list of all available enemy types"""
    return list(get_all_enemy_sprites().keys())

def generate_enemy_sprite(enemy_type="orc"):
    sprite = pygame.Surface((64, 64), pygame.SRCALPHA)
    
    if enemy_type == "orc":
        # Orc vert
        pygame.draw.circle(sprite, (100, 150, 50), (32, 50), 24)
        pygame.draw.circle(sprite, (80, 120, 40), (32, 30), 16)
        pygame.draw.circle(sprite, (255, 0, 0), (26, 26), 4)
        pygame.draw.circle(sprite, (255, 0, 0), (38, 26), 4)
        pygame.draw.ellipse(sprite, (60, 90, 30), (24, 58, 16, 6))
        pygame.draw.ellipse(sprite, (60, 90, 30), (40, 58, 16, 6))
    elif enemy_type == "skeleton":
        # Squelette blanc
        pygame.draw.circle(sprite, (240, 240, 240), (32, 50), 24)
        pygame.draw.circle(sprite, (220, 220, 220), (32, 30), 16)
        pygame.draw.circle(sprite, (0, 0, 0), (26, 26), 4)
        pygame.draw.circle(sprite, (0, 0, 0), (38, 26), 4)
        pygame.draw.ellipse(sprite, (200, 200, 200), (24, 58, 16, 6))
        pygame.draw.ellipse(sprite, (200, 200, 200), (40, 58, 16, 6))
    elif enemy_type == "goblin":
        # Gobelin rouge (plus petit)
        pygame.draw.circle(sprite, (200, 0, 0), (32, 50), 20)
        pygame.draw.circle(sprite, (150, 0, 0), (32, 30), 14)
        pygame.draw.circle(sprite, (255, 255, 0), (26, 26), 3)
        pygame.draw.circle(sprite, (255, 255, 0), (38, 26), 3)
        pygame.draw.ellipse(sprite, (120, 0, 0), (26, 58, 12, 6))
        pygame.draw.ellipse(sprite, (120, 0, 0), (38, 58, 12, 6))
    elif enemy_type == "troll":
        # Troll brun (plus grand)
        pygame.draw.circle(sprite, (139, 69, 19), (32, 48), 28)
        pygame.draw.circle(sprite, (101, 67, 33), (32, 28), 18)
        pygame.draw.circle(sprite, (255, 0, 0), (26, 24), 5)
        pygame.draw.circle(sprite, (255, 0, 0), (38, 24), 5)
        pygame.draw.ellipse(sprite, (85, 53, 15), (22, 58, 20, 6))
        pygame.draw.ellipse(sprite, (85, 53, 15), (42, 58, 20, 6))

    return sprite

def create_random_enemy(x, y):
    """Create random enemy type"""
    enemy_types = ["orc", "skeleton", "goblin", "troll"]
    enemy_type = random.choice(enemy_types)
    return Enemy(x, y, enemy_type)

def render_sprite(screen, sprite, x, y, distance, screen_height):
    """Render sprite with correct ground positioning"""
    if distance <= 0:
        return
    
    # Get original sprite dimensions to preserve aspect ratio
    original_width, original_height = sprite.get_size()
    aspect_ratio = original_width / original_height
    
    # Calculate sprite size based on distance - LARGER SIZE
    sprite_height = int(screen_height / distance * 1.5)
    sprite_width = int(sprite_height * aspect_ratio)  # Preserve aspect ratio
    
    # Scale sprite
    scaled_sprite = pygame.transform.scale(sprite, (sprite_width, sprite_height))
    
    # Position sprite on ground - bottom of sprite AT horizon line
    horizon_y = screen_height // 2
    sprite_y = horizon_y  # Bottom edge of sprite at horizon = ground level
    sprite_x = x - sprite_width // 2
    
    screen.blit(scaled_sprite, (sprite_x, sprite_y))

def cast_ray(player, angle, dungeon, max_distance=20, step=0.1):
    x, y = player.x, player.y
    dx = math.cos(angle) * step
    dy = math.sin(angle) * step
    
    steps = int(max_distance / step)
    for _ in range(steps):
        x += dx
        y += dy
        
        if dungeon.is_wall(x, y):
            distance = math.sqrt((x - player.x)**2 + (y - player.y)**2)
            return distance, x, y
    
    return max_distance, x, y

def has_line_of_sight(player, enemy, dungeon):
    dx = enemy.x - player.x
    dy = enemy.y - player.y
    distance = math.sqrt(dx*dx + dy*dy)
    
    if distance == 0:
        return True
    
    steps = max(1, int(distance * 10))
    step_x, step_y = dx / steps, dy / steps
    
    x, y = player.x, player.y
    for _ in range(steps):
        x += step_x
        y += step_y
        if dungeon.is_wall(x, y):
            return False
    
    return True

def find_path(dungeon, start, goal):
    from heapq import heappop, heappush

    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}

    while open_set:
        _, current = heappop(open_set)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor = (current[0] + dx, current[1] + dy)
            if dungeon.is_wall(neighbor[0], neighbor[1]):
                continue

            tentative_g_score = g_score[current] + 1
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                heappush(open_set, (f_score[neighbor], neighbor))

    return []

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Dungeon Explorer 3D")
        self.font = pygame.font.Font(None, 36)
        self.clock = pygame.time.Clock()

        try:
            self.enemy_sprites = load_enemy_sprites()
            self.textures = load_textures()
            base_path = os.path.dirname(__file__) + "/assets/audio/"
            self.potion_sound = pygame.mixer.Sound(os.path.join(base_path, "potion_pickup.wav"))
            self.potion_use_sound = pygame.mixer.Sound(os.path.join(base_path, "02_Heal_02.wav"))
        except Exception as e:
            print(f"Erreur de chargement des ressources : {e}")
            self.potion_sound = None
            self.potion_use_sound = None
        
        self.dungeon = None
        self.player = None
        self.enemies = []
        self.health_potions = []
        self.bullets = []

        self.start_time = None
        self.enemies_killed = 0
        self.current_level = 1  # Niveau actuel du donjon
        self.total_enemies_killed = 0  # Total des ennemis tués sur tous les niveaux

        # Chemin du fichier de sauvegarde
        self.save_file = os.path.join(os.path.dirname(__file__), "dungeon_save.json")

    def save_game(self):
        """Sauvegarde la progression du joueur"""
        try:
            save_data = {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "player_data": {
                    "level": self.player.level,
                    "xp": self.player.xp,
                    "xp_to_next_level": self.player.xp_to_next_level,
                    "hp": self.player.hp,
                    "max_hp": self.player.max_hp,
                    "potions": self.player.potions
                },
                "game_data": {
                    "current_level": self.current_level + 1,  # Sauvegarder le PROCHAIN niveau à jouer
                    "total_enemies_killed": self.total_enemies_killed
                }
            }

            with open(self.save_file, 'w') as f:
                json.dump(save_data, f, indent=2)

            print(f"Partie sauvegardée dans {self.save_file}")
            print(f"Prochain niveau à jouer : {self.current_level + 1}")
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde : {e}")
            return False

    def load_game(self):
        """Charge la progression du joueur"""
        try:
            if not os.path.exists(self.save_file):
                return False

            with open(self.save_file, 'r') as f:
                save_data = json.load(f)

            # Créer un joueur temporaire avec les données sauvegardées
            temp_player = Player3D(1, 1)
            temp_player.level = save_data["player_data"]["level"]
            temp_player.xp = save_data["player_data"]["xp"]
            temp_player.xp_to_next_level = save_data["player_data"]["xp_to_next_level"]
            temp_player.hp = save_data["player_data"]["hp"]
            temp_player.max_hp = save_data["player_data"]["max_hp"]
            temp_player.potions = save_data["player_data"]["potions"]

            # Récupérer les données de jeu
            saved_level = save_data["game_data"]["current_level"]
            self.total_enemies_killed = save_data["game_data"]["total_enemies_killed"]

            # Afficher les informations de sauvegarde
            timestamp = datetime.fromisoformat(save_data["timestamp"])
            print(f"Sauvegarde trouvée du {timestamp.strftime('%d/%m/%Y à %H:%M')}")
            print(f"Joueur niveau {temp_player.level} - Niveau de donjon {saved_level}")

            return {
                "player": temp_player,
                "level": saved_level,
                "timestamp": timestamp
            }
        except Exception as e:
            print(f"Erreur lors du chargement : {e}")
            return False

    def delete_save(self):
        """Supprime le fichier de sauvegarde"""
        try:
            if os.path.exists(self.save_file):
                os.remove(self.save_file)
                print("Sauvegarde supprimée")
                return True
        except Exception as e:
            print(f"Erreur lors de la suppression : {e}")
        return False

    def setup_dungeon(self):
        self.dungeon = Dungeon(20, 20)
        self.dungeon.generate()

    def is_valid_potion_position(self, x, y):
        """Vérifie si une position est valide pour placer une potion."""
        if self.dungeon.is_wall(x, y):
            return False
        if abs(x - self.player.x) < 1 or abs(y - self.player.y) < 1:  # Distance réduite
            return False
        if any(abs(x - e.x) < 1 and abs(y - e.y) < 1 for e in self.enemies):  # Distance réduite
            return False
        return True

    def is_near_wall(self, x, y, min_distance=2):
        """Vérifie si une position est trop proche d'un mur."""
        for dx in range(-min_distance, min_distance + 1):
            for dy in range(-min_distance, min_distance + 1):
                if self.dungeon.is_wall(x + dx, y + dy):
                    return True
        return False

    def place_potions(self, num_potions=6, max_attempts=50):
        """Place un nombre donné de potions dans le donjon."""
        self.health_potions = []
        for _ in range(num_potions):
            for _ in range(max_attempts):
                x, y = random.randint(1, self.dungeon.width - 2), random.randint(1, self.dungeon.height - 2)
                if (not self.dungeon.is_wall(x, y) and not self.is_near_wall(x, y, min_distance=2) and abs(x - self.player.x) >= 1 and abs(y - self.player.y) >= 1):
                    self.health_potions.append(HealthPotion(x, y))
                    break
        print(f"Potions ajoutées : {len(self.health_potions)}")

    def get_enemy_types_for_level(self, level):
        """Retourne les types d'ennemis disponibles selon le niveau du donjon"""
        if level == 1:
            return ["goblin", "skeleton"]  # Ennemis faciles
        elif level == 2:
            return ["skeleton", "orc"]  # Ennemis moyens
        elif level == 3:
            return ["orc", "troll"]  # Ennemis difficiles
        else:
            return ["orc", "troll", "troll"]  # Beaucoup de trolls pour les niveaux élevés

    def scale_enemies_for_level(self, level):
        """Augmente la difficulté des ennemis selon le niveau du donjon"""
        scaling_factor = (level - 1) * 0.2  # 20% d'augmentation par niveau

        for enemy in self.enemies:
            # Augmenter les HP
            bonus_hp = int(enemy.max_hp * scaling_factor)
            enemy.max_hp += bonus_hp
            enemy.hp += bonus_hp

            # Augmenter le niveau effectif pour les calculs de combat
            enemy.level += level - 1

            # Augmenter les récompenses XP
            enemy.xp_value = int(enemy.xp_value * (1 + scaling_factor))

    def place_entities_for_level(self, level, preserve_player_stats=False):
        """Place les entités en fonction du niveau, en préservant optionnellement les stats du joueur"""
        self.enemies_killed = 0

        # Créer ou réutiliser le joueur
        if not preserve_player_stats or self.player is None:
            if self.dungeon.rooms:
                room = self.dungeon.rooms[0]
                self.player = Player3D(room["x"] + 1, room["y"] + 1)
            else:
                self.player = Player3D(1, 1)
        else:
            # Repositionner le joueur au début du nouveau niveau
            if self.dungeon.rooms:
                room = self.dungeon.rooms[0]
                self.player.x = room["x"] + 1
                self.player.y = room["y"] + 1
            else:
                self.player.x, self.player.y = 1, 1
            self.player.angle = 0

        # Récupérer les types d'ennemis pour ce niveau
        available_types = self.get_enemy_types_for_level(level)

        self.enemies = []
        min_distance_from_player = 5
        min_distance_between_enemies = 2

        # Plus d'ennemis pour les niveaux élevés
        base_enemies_per_room = 1 + (level - 1) // 2
        base_corridor_enemies = 3 + (level - 1)

        # Placer des ennemis dans chaque salle (sauf la première)
        for room in self.dungeon.rooms[1:]:
            for _ in range(base_enemies_per_room):
                for attempt in range(50):
                    x = random.randint(room["x"], room["x"] + room["w"] - 1)
                    y = random.randint(room["y"], room["y"] + room["h"] - 1)

                    if not (0 <= x < self.dungeon.width and 0 <= y < self.dungeon.height):
                        continue
                    if self.dungeon.is_wall(x, y) or self.is_near_wall(x, y, min_distance=2):
                        continue
                    if math.sqrt((x - self.player.x) ** 2 + (y - self.player.y) ** 2) < min_distance_from_player:
                        continue
                    if any(math.sqrt((x - e.x) ** 2 + (y - e.y) ** 2) < min_distance_between_enemies for e in self.enemies):
                        continue

                    enemy_type = random.choice(available_types)
                    self.enemies.append(Enemy(x, y, enemy_type, available_types))
                    break

        # Ajouter des ennemis dans les couloirs
        for _ in range(base_corridor_enemies):
            for attempt in range(50):
                x = random.randint(1, self.dungeon.width - 2)
                y = random.randint(1, self.dungeon.height - 2)

                if not (0 <= x < self.dungeon.width and 0 <= y < self.dungeon.height):
                    continue
                if self.dungeon.is_wall(x, y):
                    continue
                if math.sqrt((x - self.player.x) ** 2 + (y - self.player.y) ** 2) < min_distance_from_player:
                    continue
                if any(math.sqrt((x - e.x) ** 2 + (y - e.y) ** 2) < min_distance_between_enemies for e in self.enemies):
                    continue

                enemy_type = random.choice(available_types)
                self.enemies.append(Enemy(x, y, enemy_type, available_types))
                break

        # Appliquer le scaling de difficulté
        self.scale_enemies_for_level(level)

        # Ajouter plus de potions pour les niveaux élevés
        potion_count = 6 + (level - 1) * 2
        self.health_potions = []
        for _ in range(potion_count):
            for attempt in range(50):
                x, y = random.randint(1, self.dungeon.width - 2), random.randint(1, self.dungeon.height - 2)
                if (not self.dungeon.is_wall(x, y) and abs(x - self.player.x) >= 1 and abs(y - self.player.y) >= 1 and
                        all(abs(x - e.x) >= 1 and abs(y - e.y) >= 1 for e in self.enemies)):
                    self.health_potions.append(HealthPotion(x, y))
                    break

        print(f"Niveau {level}: {len(self.enemies)} ennemis, {len(self.health_potions)} potions")
        print(f"Types d'ennemis disponibles: {available_types}")

    def place_entities(self):
        self.enemies_killed = 0  # Réinitialiser le compteur d'ennemis tués
        if self.dungeon.rooms:
            room = self.dungeon.rooms[0]
            self.player = Player3D(room["x"] + 1, room["y"] + 1)
        else:
            self.player = Player3D(1, 1)

        self.enemies = []
        available_types = get_available_enemy_types()
        min_distance_from_player = 5  # Distance minimale entre le joueur et les monstres
        min_distance_between_enemies = 2  # Distance minimale entre les monstres

        # Placer un ennemi par salle (sauf la première)
        for room in self.dungeon.rooms[1:]:
            for _ in range(50):  # Limiter les tentatives de placement
                x = random.randint(room["x"], room["x"] + room["w"] - 1)
                y = random.randint(room["y"], room["y"] + room["h"] - 1)

                if not (0 <= x < self.dungeon.width and 0 <= y < self.dungeon.height):
                    continue
                if self.dungeon.is_wall(x, y) or self.is_near_wall(x, y, min_distance=2):
                    continue
                if math.sqrt((x - self.player.x) ** 2 + (y - self.player.y) ** 2) < min_distance_from_player:
                    continue
                if any(math.sqrt((x - e.x) ** 2 + (y - e.y) ** 2) < min_distance_between_enemies for e in self.enemies):
                    continue

                self.enemies.append(Enemy(x, y, available_types=available_types))
                break

        # Ajouter quelques ennemis dans les couloirs
        for _ in range(3):
            for _ in range(50):  # Limiter les tentatives de placement
                x = random.randint(1, self.dungeon.width - 2)
                y = random.randint(1, self.dungeon.height - 2)

                if not (0 <= x < self.dungeon.width and 0 <= y < self.dungeon.height):
                    continue
                if self.dungeon.is_wall(x, y):
                    continue
                if math.sqrt((x - self.player.x) ** 2 + (y - self.player.y) ** 2) < min_distance_from_player:
                    continue
                if any(math.sqrt((x - e.x) ** 2 + (y - e.y) ** 2) < min_distance_between_enemies for e in self.enemies):
                    continue

                self.enemies.append(Enemy(x, y, available_types=available_types))
                break

        # Ajouter les potions
        self.health_potions = []
        for _ in range(6):  # Nombre de potions à placer
            for _ in range(50):  # Limiter les tentatives de placement
                x, y = random.randint(1, self.dungeon.width - 2), random.randint(1, self.dungeon.height - 2)
                if (not self.dungeon.is_wall(x, y) and abs(x - self.player.x) >= 1 and abs(y - self.player.y) >= 1 and
                        all(abs(x - e.x) >= 1 and abs(y - e.y) >= 1 for e in self.enemies)):  # Distance réduite
                    self.health_potions.append(HealthPotion(x, y))
                    break

        # Vérification des potions ajoutées
        # print(f"Potions ajoutées : {[{'x': p.x, 'y': p.y} for p in self.health_potions]}")
        print(f"Potions ajoutées : {len(self.health_potions)}")

    def handle_input(self, keys):
        if keys[pygame.K_z]:
            self.player.move(math.cos(self.player.angle), math.sin(self.player.angle), self.dungeon)
        if keys[pygame.K_s]:
            self.player.move(-math.cos(self.player.angle), -math.sin(self.player.angle), self.dungeon)
        if keys[pygame.K_q]:
            self.player.rotate(-0.05)
        if keys[pygame.K_d]:
            self.player.rotate(0.05)
        if keys[pygame.K_LEFT]:
            self.player.move(math.cos(self.player.angle - math.pi/2), math.sin(self.player.angle - math.pi/2), self.dungeon)
        if keys[pygame.K_RIGHT]:
            self.player.move(math.cos(self.player.angle + math.pi/2), math.sin(self.player.angle + math.pi/2), self.dungeon)
        if keys[pygame.K_p]:
            self.player.use_potion(self.potion_use_sound)

    def update_bullets(self):
        for bullet in self.bullets[:]:
            if not bullet.update(self.dungeon):
                self.bullets.remove(bullet)
                continue
            
            if bullet.is_player_bullet:
                for enemy in self.enemies[:]:
                    if abs(bullet.x - enemy.x) < 0.3 and abs(bullet.y - enemy.y) < 0.3:
                        # Vérifier si l'attaque du joueur réussit
                        if self.player.roll_attack(enemy.level):
                            # L'attaque réussit, calculer les dégâts
                            damage = self.player.roll_damage()
                            enemy_killed = enemy.take_damage(damage)

                            print(f"Touché! Dégâts: {damage} HP (Ennemi {enemy.enemy_type} niveau {enemy.level}: {enemy.hp}/{enemy.max_hp} HP)")

                            if enemy_killed:
                                # Attribuer l'XP au joueur
                                xp_gained = enemy.xp_value
                                leveled_up = self.player.gain_xp(xp_gained)
                                print(f"Ennemi {enemy.enemy_type} tué! +{xp_gained} XP")

                                if leveled_up:
                                    print(f"NIVEAU SUPÉRIEUR! Niveau {self.player.level}")

                                self.enemies.remove(enemy)
                                self.enemies_killed += 1
                        else:
                            # L'attaque a raté
                            print(f"Attaque ratée contre {enemy.enemy_type} niveau {enemy.level}")
                            enemy.hit_animation = 5  # Animation plus courte pour les attaques ratées

                        self.bullets.remove(bullet)
                        break
            else:
                # Balle ennemie
                if abs(bullet.x - self.player.x) < 0.3 and abs(bullet.y - self.player.y) < 0.3:
                    # Trouver l'ennemi qui a tiré cette balle (approximation)
                    closest_enemy = None
                    min_distance = float('inf')
                    for enemy in self.enemies:
                        dist = math.sqrt((bullet.x - enemy.x)**2 + (bullet.y - enemy.y)**2)
                        if dist < min_distance:
                            min_distance = dist
                            closest_enemy = enemy

                    if closest_enemy and closest_enemy.roll_attack(self.player.level):
                        # L'attaque de l'ennemi réussit
                        damage = closest_enemy.roll_damage()
                        self.player.take_damage(damage)
                        print(f"Touché par {closest_enemy.enemy_type}! Dégâts: {damage} HP (Joueur: {self.player.hp}/{self.player.max_hp} HP)")
                    else:
                        print(f"L'attaque de l'ennemi a raté!")

                    self.bullets.remove(bullet)

    def collect_potions(self):
        for potion in self.health_potions[:]:
            if abs(self.player.x - potion.x) < 0.5 and abs(self.player.y - potion.y) < 0.5:
                self.player.potions += 1
                self.health_potions.remove(potion)
                if self.potion_sound:  # Vérifier si le son est chargé
                    self.potion_sound.set_volume(0.4)
                    self.potion_sound.play()

    def show_instructions(self):
        self.screen.fill((0, 0, 0))

        # Vérifier s'il y a une sauvegarde
        save_data = self.load_game()

        instructions = [
            "DUNGEON EXPLORER 3D",
            "",
            "CONTROLES:",
            "Z/S - Avancer/Reculer",
            "Q/D - Tourner gauche/droite",
            "Flèches - Déplacement latéral",
            "Clic gauche - Tirer sur les ennemis",
            "P - Utiliser une potion",
            "",
            "Éliminez tous les ennemis!",
            "",
        ]

        # Ajouter les options de jeu
        if save_data:
            instructions.extend([
                f"Sauvegarde trouvée du {save_data['timestamp'].strftime('%d/%m/%Y à %H:%M')}:",
                f"Joueur niveau {save_data['player'].level} - Niveau donjon {save_data['level']}",
                "",
                "L - Charger la partie sauvegardée",
                "N - Nouvelle partie",
                "",
                "Appuyez sur L ou N pour choisir"
            ])
        else:
            instructions.extend([
                "Appuyez sur ESPACE pour commencer"
            ])

        for i, line in enumerate(instructions):
            if i == 0:  # Titre
                color = (255, 255, 0)
            elif "Sauvegarde trouvée" in line:
                color = (0, 255, 0)
            elif line.startswith("Joueur niveau"):
                color = (255, 255, 0)
            elif line.startswith(("L -", "N -")):
                color = (0, 200, 255)
            else:
                color = (255, 255, 255)

            text = self.font.render(line, True, color)
            text_rect = text.get_rect(center=(self.screen.get_width()//2, 80 + i*25))
            self.screen.blit(text, text_rect)
        
        pygame.display.flip()

        # Attendre le choix du joueur
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                elif event.type == pygame.KEYDOWN:
                    if save_data:
                        if event.key == pygame.K_l:
                            return "load"
                        elif event.key == pygame.K_n:
                            return "new"
                    else:
                        if event.key == pygame.K_SPACE:
                            return "new"

    def show_end_screen(self, message, color, enemies_killed, elapsed_time):
        self.screen.fill((0, 0, 0))
        title_text = self.font.render(message, True, color)
        kills_text = self.font.render(f"Ennemis tués : {enemies_killed}", True, (255, 255, 255))
        time_text = self.font.render(f"Temps écoulé : {elapsed_time}s", True, (255, 255, 255))
        restart_text = pygame.font.Font(None, 24).render("Appuyez sur R pour rejouer ou ESC pour quitter", True, (255, 255, 255))

        title_rect = title_text.get_rect(center=(400, 240))
        kills_rect = kills_text.get_rect(center=(400, 280))
        time_rect = time_text.get_rect(center=(400, 320))
        restart_rect = restart_text.get_rect(center=(400, 360))

        self.screen.blit(title_text, title_rect)
        self.screen.blit(kills_text, kills_rect)
        self.screen.blit(time_text, time_rect)
        self.screen.blit(restart_text, restart_rect)
        pygame.display.flip()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    return True

    def show_victory_screen(self, enemies_killed, elapsed_time):
        """Affiche l'écran de victoire avec option de continuer au niveau suivant"""
        self.screen.fill((0, 0, 0))

        # Calculer les statistiques du niveau
        self.total_enemies_killed += enemies_killed

        # Titre de victoire
        title_text = self.font.render(f"NIVEAU {self.current_level} TERMINÉ!", True, (0, 255, 0))
        title_rect = title_text.get_rect(center=(400, 160))
        self.screen.blit(title_text, title_rect)

        # Statistiques du niveau
        stats_font = pygame.font.Font(None, 28)
        level_kills_text = stats_font.render(f"Ennemis tués ce niveau : {enemies_killed}", True, (255, 255, 255))
        level_kills_rect = level_kills_text.get_rect(center=(400, 200))
        self.screen.blit(level_kills_text, level_kills_rect)

        time_text = stats_font.render(f"Temps écoulé : {elapsed_time}s", True, (255, 255, 255))
        time_rect = time_text.get_rect(center=(400, 230))
        self.screen.blit(time_text, time_rect)

        total_kills_text = stats_font.render(f"Total ennemis tués : {self.total_enemies_killed}", True, (255, 255, 255))
        total_kills_rect = total_kills_text.get_rect(center=(400, 260))
        self.screen.blit(total_kills_text, total_kills_rect)

        # Statistiques du joueur
        player_stats_text = stats_font.render(f"Joueur - Niveau: {self.player.level} | HP: {self.player.hp}/{self.player.max_hp} | Potions: {self.player.potions}", True, (255, 255, 0))
        player_stats_rect = player_stats_text.get_rect(center=(400, 300))
        self.screen.blit(player_stats_text, player_stats_rect)

        # Options avec sauvegarde
        continue_text = pygame.font.Font(None, 24).render(f"C - Continuer au NIVEAU {self.current_level + 1}", True, (0, 255, 0))
        continue_rect = continue_text.get_rect(center=(400, 350))
        self.screen.blit(continue_text, continue_rect)

        save_text = pygame.font.Font(None, 24).render("S - Sauvegarder et continuer", True, (0, 200, 255))
        save_rect = save_text.get_rect(center=(400, 375))
        self.screen.blit(save_text, save_rect)

        restart_text = pygame.font.Font(None, 24).render("R - Recommencer depuis le niveau 1", True, (255, 255, 0))
        restart_rect = restart_text.get_rect(center=(400, 400))
        self.screen.blit(restart_text, restart_rect)

        quit_text = pygame.font.Font(None, 24).render("ESC - Quitter le jeu", True, (255, 100, 100))
        quit_rect = quit_text.get_rect(center=(400, 425))
        self.screen.blit(quit_text, quit_rect)

        pygame.display.flip()

        # Boucle d'attente des choix
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return "quit"
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                    return "continue"
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:
                    # Sauvegarder et continuer
                    if self.save_game():
                        # Afficher message de confirmation
                        confirm_text = pygame.font.Font(None, 24).render("Partie sauvegardée ! Appuyez sur une touche...", True, (0, 255, 0))
                        confirm_rect = confirm_text.get_rect(center=(400, 460))
                        self.screen.blit(confirm_text, confirm_rect)
                        pygame.display.flip()
                        pygame.time.wait(2000)
                    return "continue"
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    return "restart"

    def show_death_screen(self, enemies_killed, elapsed_time):
        """Affiche l'écran de mort avec statistiques"""
        self.screen.fill((0, 0, 0))

        title_text = self.font.render("VOUS ÊTES MORT!", True, (255, 0, 0))
        title_rect = title_text.get_rect(center=(400, 200))
        self.screen.blit(title_text, title_rect)

        stats_font = pygame.font.Font(None, 28)
        level_text = stats_font.render(f"Niveau atteint : {self.current_level}", True, (255, 255, 255))
        level_rect = level_text.get_rect(center=(400, 250))
        self.screen.blit(level_text, level_rect)

        kills_text = stats_font.render(f"Total ennemis tués : {self.total_enemies_killed + enemies_killed}", True, (255, 255, 255))
        kills_rect = kills_text.get_rect(center=(400, 280))
        self.screen.blit(kills_text, kills_rect)

        time_text = stats_font.render(f"Temps de survie : {elapsed_time}s", True, (255, 255, 255))
        time_rect = time_text.get_rect(center=(400, 310))
        self.screen.blit(time_text, time_rect)

        restart_text = pygame.font.Font(None, 24).render("R - Recommencer | ESC - Quitter", True, (255, 255, 255))
        restart_rect = restart_text.get_rect(center=(400, 380))
        self.screen.blit(restart_text, restart_rect)

        pygame.display.flip()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    return True

    def start_new_level(self, level, preserve_stats=False):
        """Démarre un nouveau niveau"""
        self.current_level = level
        self.setup_dungeon()
        self.place_entities_for_level(level, preserve_stats)
        self.bullets = []
        self.start_time = pygame.time.get_ticks()

        print(f"=== NIVEAU {level} ===")
        if preserve_stats:
            print(f"Joueur niveau {self.player.level} avec {self.player.hp}/{self.player.max_hp} HP")
        print(f"Difficulté augmentée, {len(self.enemies)} ennemis à affronter!")

    def render_walls(self, width, height):
        for x in range(0, width, 2):
            angle = self.player.angle - self.player.fov / 2 + (x / width) * self.player.fov
            distance, hit_x, hit_y = cast_ray(self.player, angle, self.dungeon)
            distance *= math.cos(angle - self.player.angle)
            if distance > 0:
                wall_height = int(height / (distance + 0.1))
                wall_top = (height - wall_height) // 2
                wall_bottom = wall_top + wall_height
                wall_x = hit_x - math.floor(hit_x)
                if abs(math.cos(angle)) > abs(math.sin(angle)):
                    wall_x = hit_y - math.floor(hit_y)
                base_color = 120 if int(wall_x * 8) % 2 == 0 else 100
                brightness = max(50, 255 - int(distance * 12))
                color = (min(255, base_color + brightness // 3), min(255, base_color // 2 + brightness // 4), min(255, base_color // 3 + brightness // 5))
                pygame.draw.line(self.screen, color, (x, wall_top), (x, wall_bottom), 2)

    def render_player_ui(self, width, height):
        debug_font = pygame.font.Font(None, 24)
        player_debug = debug_font.render(f"Player: ({self.player.x:.1f}, {self.player.y:.1f}, {self.player.z:.1f})", True, (255, 255, 0))
        self.screen.blit(player_debug, (10, height - 60))
        enemy_count = debug_font.render(f"Enemies visible: {len([e for e in self.enemies if math.sqrt((e.x - self.player.x) ** 2 + (e.y - self.player.y) ** 2) < 10])}", True, (255, 255, 0))
        self.screen.blit(enemy_count, (10, height - 40))
        health_bar_width = 200
        health_bar_height = 20
        health_x = width - health_bar_width - 10
        health_y = 10
        pygame.draw.rect(self.screen, (100, 0, 0), (health_x, health_y, health_bar_width, health_bar_height))
        health_ratio = self.player.hp / self.player.max_hp
        health_width = int(health_bar_width * health_ratio)
        pygame.draw.rect(self.screen, (0, 255, 0), (health_x, health_y, health_width, health_bar_height))
        pygame.draw.rect(self.screen, (255, 255, 255), (health_x, health_y, health_bar_width, health_bar_height), 2)
        font = pygame.font.Font(None, 24)
        hp_text = font.render(f"HP: {self.player.hp}/{self.player.max_hp}", True, (255, 255, 255))
        self.screen.blit(hp_text, (health_x, health_y + health_bar_height + 5))
        potion_text = font.render(f"Potions: {self.player.potions}", True, (0, 255, 0))
        self.screen.blit(potion_text, (health_x - 120, health_y + 5))

        # Afficher le niveau et l'XP
        level_text = font.render(f"Niveau: {self.player.level}", True, (255, 255, 255))
        self.screen.blit(level_text, (health_x - 120, health_y + 30))
        xp_percentage = self.player.get_xp_percentage()
        pygame.draw.rect(self.screen, (100, 100, 255), (health_x, health_y + health_bar_height + 25, health_bar_width, health_bar_height))
        pygame.draw.rect(self.screen, (255, 255, 0), (health_x, health_y + health_bar_height + 25, health_bar_width * xp_percentage, health_bar_height))
        xp_text = font.render(f"XP: {self.player.xp}/{self.player.xp_to_next_level}", True, (255, 255, 255))
        self.screen.blit(xp_text, (health_x, health_y + health_bar_height + 50))

        center_x, center_y = width // 2, height // 2
        crosshair_size = 10
        crosshair_color = (255, 255, 255) if self.player.shoot_cooldown == 0 else (255, 0, 0)
        pygame.draw.line(self.screen, crosshair_color, (center_x - crosshair_size, center_y), (center_x + crosshair_size, center_y), 2)
        pygame.draw.line(self.screen, crosshair_color, (center_x, center_y - crosshair_size), (center_x, center_y + crosshair_size), 2)
        if self.player.shoot_flash > 0:
            flash_intensity = self.player.shoot_flash / 8.0
            flash_size = int(30 * flash_intensity)
            flash_color = (255, int(255 * flash_intensity), 0)
            pygame.draw.circle(self.screen, flash_color, (center_x, center_y), flash_size // 2)
            for i in range(5):
                particle_x = center_x + random.randint(-flash_size, flash_size)
                particle_y = center_y + random.randint(-flash_size // 2, flash_size // 2)
                particle_size = max(1, int(flash_size // 4 * flash_intensity))
                pygame.draw.circle(self.screen, (255, 200, 0), (particle_x, particle_y), particle_size)

    def render_3d(self):
        width, height = self.screen.get_size()
        self.screen.fill((50, 50, 100))
        pygame.draw.rect(self.screen, (100, 50, 0), (0, height // 2, width, height // 2))
        self.render_walls(width, height)
        for enemy in self.enemies:
            self.render_entity(enemy, width, height)
        for potion in self.health_potions:
            self.render_potion(potion, width, height)
        for bullet in self.bullets:
            self.render_bullet(bullet, width, height)
        self.render_player_ui(width, height)

    def render_entity(self, enemy, width, height):
        distance, angle_diff, screen_x = get_perspective_params(enemy.x, enemy.y, self.player, width, height)
        if distance < 10 and abs(angle_diff) < self.player.fov / 2 and has_line_of_sight(self.player, enemy, self.dungeon):
            sprite_surface = self.enemy_sprites.get(enemy.enemy_type, self.enemy_sprites.get('orc', generate_enemy_sprite()))
            original_width, original_height = sprite_surface.get_size()
            aspect_ratio = original_width / original_height
            real_height = enemy.height
            perspective_scale = 1.0 / (distance + 0.1)
            screen_height_px = max(40, int(real_height * 200 * perspective_scale))
            screen_width_px = int(screen_height_px * aspect_ratio)
            eye_level_y = height // 2
            vertical_offset = int(self.player.eye_height * VERTICAL_PERSPECTIVE_FACTOR / (distance + 0.1))
            ground_level_y = eye_level_y + vertical_offset
            sprite_y = ground_level_y - screen_height_px
            sprite_x = screen_x - screen_width_px // 2
            if 0 <= screen_x < width and screen_height_px > 10:
                scaled_sprite = pygame.transform.scale(sprite_surface, (screen_width_px, screen_height_px))
                brightness = max(0.3, 1.0 - distance / 10)
                dark_sprite = scaled_sprite.copy()
                if enemy.hit_animation > 0:
                    hit_intensity = enemy.hit_animation / 10.0
                    red_tint = (255, int(100 * hit_intensity), int(100 * hit_intensity))
                    dark_sprite.fill(red_tint, special_flags=pygame.BLEND_MULT)
                else:
                    dark_sprite.fill((int(255 * brightness), int(255 * brightness), int(255 * brightness)), special_flags=pygame.BLEND_MULT)
                self.screen.blit(dark_sprite, (sprite_x, sprite_y))

                # Barre d'HP au-dessus de l'ennemi
                if enemy.hp < enemy.max_hp:
                    bar_width = screen_width_px
                    bar_height = max(4, screen_width_px // 10)
                    bar_x = sprite_x
                    bar_y = sprite_y - bar_height - 5

                    # Barre de fond (rouge)
                    pygame.draw.rect(self.screen, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))

                    # Barre de HP (verte)
                    hp_ratio = enemy.hp / enemy.max_hp
                    hp_width = int(bar_width * hp_ratio)
                    pygame.draw.rect(self.screen, (0, 255, 0), (bar_x, bar_y, hp_width, bar_height))

                    # Contour de la barre
                    pygame.draw.rect(self.screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 1)

    def render_potion(self, potion, width, height):
        distance, angle_diff, screen_x = get_perspective_params(potion.x, potion.y, self.player, width, height)
        if distance < 8 and abs(angle_diff) < self.player.fov / 2 and has_line_of_sight(self.player, potion, self.dungeon):
            real_height = 0.3
            perspective_scale = 1.0 / (distance + 0.1)
            potion_size = max(20, int(real_height * 200 * perspective_scale))
            eye_level_y = height // 2
            vertical_offset = int(self.player.eye_height * VERTICAL_PERSPECTIVE_FACTOR / (distance + 0.1))
            ground_level_y = eye_level_y + vertical_offset
            sprite_bottom = ground_level_y
            potion_y = sprite_bottom - potion_size
            if 0 <= screen_x < width and potion_size > 5:
                pygame.draw.circle(self.screen, (0, 255, 0), (screen_x, potion_y + potion_size // 2), potion_size // 3)
                pygame.draw.line(self.screen, (255, 255, 255), (screen_x - potion_size // 4, potion_y + potion_size // 2), (screen_x + potion_size // 4, potion_y + potion_size // 2), 3)
                pygame.draw.line(self.screen, (255, 255, 255), (screen_x, potion_y + potion_size // 2 - potion_size // 4), (screen_x, potion_y + potion_size // 2 + potion_size // 4), 3)

    def render_bullet(self, bullet, width, height):
        distance, angle_diff, screen_x = get_perspective_params(bullet.x, bullet.y, self.player, width, height)
        if distance < 8 and abs(angle_diff) < self.player.fov / 2:
            bullet_size = max(3, int(20 / (distance + 0.1)))
            bullet_y = height // 2
            if 0 <= screen_x < width:
                bullet_color = (255, 255, 0) if bullet.is_player_bullet else (255, 100, 100)
                pygame.draw.circle(self.screen, bullet_color, (screen_x, bullet_y), bullet_size)

    def draw_minimap(self):
        mini_size = 150
        mini_scale = mini_size / max(self.dungeon.width, self.dungeon.height)
        pygame.draw.rect(self.screen, (0, 0, 0), (10, 10, mini_size, mini_size))

        # Dessiner les murs
        for y in range(self.dungeon.height):
            for x in range(self.dungeon.width):
                if self.dungeon.grid[y][x] != 0:
                    pygame.draw.rect(self.screen, (100, 100, 100), (10 + x * mini_scale, 10 + y * mini_scale, mini_scale, mini_scale))

        # Dessiner le joueur
        player_map_x = int(10 + self.player.x * mini_scale)
        player_map_y = int(10 + self.player.y * mini_scale)
        pygame.draw.circle(self.screen, (255, 255, 0), (player_map_x, player_map_y), 3)

        # Dessiner les ennemis
        for enemy in self.enemies:
            enemy_map_x = int(10 + enemy.x * mini_scale)
            enemy_map_y = int(10 + enemy.y * mini_scale)
            pygame.draw.circle(self.screen, (255, 0, 0), (enemy_map_x, enemy_map_y), 2)

        # Dessiner les potions
        for potion in self.health_potions:
            potion_map_x = int(10 + potion.x * mini_scale)
            potion_map_y = int(10 + potion.y * mini_scale)
            pygame.draw.circle(self.screen, (0, 255, 0), (potion_map_x, potion_map_y), 2)

        # Afficher le niveau du donjon et les statistiques
        elapsed_time = (pygame.time.get_ticks() - self.start_time) // 1000
        level_text = pygame.font.Font(None, 20).render(f"NIVEAU {self.current_level}", True, (255, 255, 0))
        time_text = pygame.font.Font(None, 20).render(f"Temps: {elapsed_time}s", True, (255, 255, 255))
        kills_text = pygame.font.Font(None, 20).render(f"Tués: {self.enemies_killed}", True, (255, 255, 255))

        self.screen.blit(level_text, (10 + mini_size + 10, 10))
        self.screen.blit(time_text, (10 + mini_size + 10, 30))
        self.screen.blit(kills_text, (10 + mini_size + 10, 50))

    def run(self):
        choice = self.show_instructions()
        if choice is None:  # L'utilisateur a fermé la fenêtre
            return

        if choice == "load":
            # Charger la sauvegarde
            save_data = self.load_game()
            if save_data:
                # Restaurer les données du joueur
                self.player = save_data["player"]
                self.current_level = save_data["level"]
                self.total_enemies_killed = save_data.get("total_enemies_killed", 0)

                print(f"Partie chargée : Niveau {self.player.level}, Donjon {self.current_level}")

                # Démarrer au niveau sauvegardé
                self.setup_dungeon()
                # Positionner le joueur dans le donjon
                if self.dungeon.rooms:
                    room = self.dungeon.rooms[0]
                    self.player.x = room["x"] + 1
                    self.player.y = room["y"] + 1
                else:
                    self.player.x, self.player.y = 1, 1
                self.player.angle = 0

                # Placer les entités pour ce niveau
                self.place_entities_for_level(self.current_level, preserve_player_stats=True)
            else:
                print("Erreur lors du chargement, nouvelle partie...")
                self.setup_dungeon()
                self.place_entities()
        else:
            # Nouvelle partie
            self.setup_dungeon()
            self.place_entities()

        self.bullets = []
        self.start_time = pygame.time.get_ticks()

        running = True
        while running:
            keys = pygame.key.get_pressed()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_x, mouse_y = event.pos
                    bullet = self.player.shoot(mouse_x, mouse_y, 800, 600, self.enemies, self.dungeon)
                    if bullet:
                        self.bullets.append(bullet)

            self.handle_input(keys)

            if not self.enemies:
                elapsed_time = (pygame.time.get_ticks() - self.start_time) // 1000
                action = self.show_victory_screen(self.enemies_killed, elapsed_time)
                if action == "continue":
                    self.start_new_level(self.current_level + 1, preserve_stats=True)
                elif action == "restart":
                    self.run()
                    return
                else:
                    running = False
                continue

            self.player.update()
            self.collect_potions()
            self.update_bullets()

            for enemy in self.enemies:
                bullet = enemy.update(self.player, self.dungeon, self.enemies)
                if bullet:
                    self.bullets.append(bullet)

            if self.player.hp <= 0:
                elapsed_time = (pygame.time.get_ticks() - self.start_time) // 1000
                action = self.show_death_screen(self.enemies_killed, elapsed_time)
                if action:
                    self.run()
                    return
                else:
                    running = False

            self.render_3d()
            self.draw_minimap()

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


def get_perspective_params(obj_x, obj_y, player, width, height):
    dx = obj_x - player.x
    dy = obj_y - player.y
    distance = math.sqrt(dx * dx + dy * dy)
    angle = math.atan2(dy, dx)
    angle_diff = angle - player.angle
    while angle_diff > math.pi:
        angle_diff -= 2 * math.pi
    while angle_diff < -math.pi:
        angle_diff += 2 * math.pi
    screen_x = int(width / 2 + (angle_diff / (player.fov / 2)) * width / 2)
    return distance, angle_diff, screen_x

if __name__ == "__main__":
    game = Game()
    game.run()
